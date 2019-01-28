#!/usr/bin/env python3
import os
import sys
import platform
import pickle
import toml
from .project import project
from .signing import signing

def main():
	# Retrieve entire configuration from local configuration file
	try:
		with open("syncall.toml", "r") as file:
			content = file.read()
			config = toml.loads(content)
	# With no config file we gracefully start a blank config
	except FileNotFoundError:
		config = {}

	# We store the running config on a dictionary for ease on accesing the data
	rconfig = {
		"fetch": "",
		"preserve": "",
		"build": "",
		"retry": "",
		"force": ""
	}
	# Initialize running config with falling back values
	defconfig = config.get("default", {})
	rconfig["fetch"] = defconfig.get("fetch", True)
	rconfig["preserve"] = defconfig.get("preserve", False)
	rconfig["build"] = defconfig.get("build", False)
	rconfig["retry"] = defconfig.get("retry", False)
	rconfig["keystore"] = defconfig.get("keystore", False)
	rconfig["keyalias"] = defconfig.get("keyalias", False)
	rconfig["deploy"] = defconfig.get("deploy", [])
	rconfig["force"] = []

	# This dictionary will contain the keystore/password used for each projects, plus the default for all of them
	keystores = config.get("keystores", {})

	# Basic lists of produced outputs, failed projects from current and previous iteration and available folders
	releases = []
	failed = []
	rebuild = []
	projects = os.listdir()
	workdir = os.getcwd()

	# Default to gradle wrapper, then override on project basis if the script is not found
	command = "./gradlew"
	# On Windows the gradle script is written in batch so we append proper extension
	if "Windows" in platform.system():
		command += ".bat"

	# Create the out directory in case it doesn't exist already
	if not os.path.isdir("SYNCALL-RELEASES"):
		os.mkdir("SYNCALL-RELEASES")

	# Check every argument and store arguments
	for i, arg in enumerate(sys.argv):
		# Skip first iteration (script name)
		if i == 0:
			continue
		# We expect them to be splited in key/value pairs by a single equal symbol
		arg = arg.split("=")
		# Check both pair members exist.
		try:
			name = arg[0].lstrip("--")
			value = arg[1]
		# If not, report back and exit
		except IndexError:
			print("The argument " + arg[0] + " needs a value.")
			sys.exit(1)
		else:
			# Most arguments are boolean and follow the same logic
			if name in rconfig:
				if value == "y" and name not in ["deploy", "force"]:
					rconfig[name] = True
				elif value == "n" and not name == "force":
					if name == "deploy":
						rconfig["deploy"] = []
					else:
						rconfig[name] = False
				else:
					# In the case of build/force we save a keystore/list respectively
					if name == "build":
						rconfig["build"] = True
						value = value.split(",")
						try:
							keystores["overridestore"] = {
								"path": value[0],
								"aliases": {
									value[1]: {
										"used": True
									}
								},
								"used": True
							}
							rconfig["keystore"] = "overridestore"
							rconfig["keyalias"] = value[1]
						except IndexError:
							print("No alias was given for keystore " + value[0] + " provided through command line")
							sys.exit(1)
					elif name in ["deploy", "force"]:
						rconfig[name] = value.split(",")
					else:
						print("The argument " + arg[0] + " is expected boolean (y|n). Received: " + value)
						sys.exit(1)

	# Update keystores dict twice, first with enabled projects, and then with retrieved secrets
	keystores = signing.enable(config, projects, keystores, rconfig)
	keystores = signing.secrets(keystores)

	# Retrieve list of the previously failed to build projects if retrying
	if rconfig["retry"]:
		try:
			with open(".retry-projects", "rb") as file:
				rebuild = pickle.load(file)
		# Restart the list if no previous file is found
		except FileNotFoundError:
			pass

	# Loop for every folder that is a git repository on invocation dir
	for name in projects:
		if os.path.isdir(name) and ".git" in os.listdir(name):
			os.chdir(name)
			# Retrieve custom configuration for project
			cconfig = config.get(name, {})
			# Overwrite configuration with custom values
			fetch = cconfig.get("fetch", rconfig["fetch"])
			preserve = cconfig.get("preserve", rconfig["preserve"])
			build = cconfig.get("build", rconfig["build"])
			# In case of forcing we ignore custom config if command line options have been received
			if name in rconfig["force"]:
				force = True
			else:
				force = cconfig.get("force", False)
			# Open logfile to store all the output
			with open("log.txt", "w+") as logfile:
				# Sync the project
				changed = False
				if fetch:
					changed = project.sync(name, preserve, logfile)
				# Only attempt gradle projects with build enabled and are either forced, retrying or have new changes
				if build and (changed or (rconfig["retry"] and name in rebuild) or force):
					# Get tasks defined on custom config or fallback to basic assembling of a release
					tasks = cconfig.get("tasks", ["assembleRelease"])
					result = project.build(command, tasks, logfile)
					# If some task went wrong we report it
					if result == 1:
						failed.append(name)
					# Else we search for apks to sign and merge them to the current list
					elif result == 0:
						signinfo = keystores.get(cconfig.get("keystore", rconfig["keystore"]), {})
						alias = cconfig.get("keyalias", rconfig["keyalias"])
						if signinfo["used"] and signinfo["aliases"][alias]["used"]:
							apks = project.sign(name, workdir, signinfo, alias, logfile)
							# We remember and deploy if we built something
							if len(apks) > 0:
								releases += apks
								# Retrieve possible targets for deployment
								targets = cconfig.get("deploy", rconfig["deploy"])
								# Proceed if we at least have one target
								if len(targets) > 0:
									project.deploy(apks, targets, workdir, logfile)
			# Go back to the invocation directory before moving onto the next project
			os.chdir(workdir)
	# Write to the file which projects have build failures
	with open('.retry-projects', 'wb') as file:
		pickle.dump(failed, file)
	# Provide information about the projects that have available updates
	if len(releases) > 0:
		print("\nProjects successfully built these files:")
		for value in releases:
			print("- " + value)
	# Provide information about which projects had failures
	if len(failed) > 0:
		print("\nProjects failed producing these logs:")
		for value in failed:
			print("- " + value + "/log.txt")
