#!/usr/bin/env python3
import os
import sys
import copy
import platform
import json
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
	rconfig = {}
	# Initialize running config with falling back values
	defconfig = config.get("default", {})
	rconfig["fetch"] = defconfig.get("fetch", True)
	rconfig["preserve"] = defconfig.get("preserve", False)
	rconfig["build"] = defconfig.get("build", False)
	rconfig["tasks"] = defconfig.get("tasks", ["assembleRelease"])
	rconfig["retry"] = defconfig.get("retry", False)
	rconfig["keystore"] = defconfig.get("keystore", False)
	rconfig["keyalias"] = defconfig.get("keyalias", False)
	rconfig["deploy"] = defconfig.get("deploy", [])
	rconfig["force"] = []

	# This dictionary will contain the keystore/password used for each projects, plus the default for all of them
	keystores = config.get("keystores", {})
	# Store the dictionary so a retry attempt will use the same keystores
	failed = {"keystores": copy.deepcopy(keystores)}
	# List of available projects on the current workdir, also saved
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

	# Import previously failed list of projects if retry is set
	if rconfig["retry"]:
		try:
			with open(".last-syncall", "r") as file:
				config = json.load(file)
				# Overwrite keystores to use with the ones from the previous iteration
				keystores = config.get("keystores", {})
		except FileNotFoundError:
			pass

	# Enable the keystores and keys that will be used
	keystores = signing.enable(config, projects, keystores, rconfig)
	# For the enabled projects prompt and store passwords
	keystores = signing.secrets(keystores)

	# Loop for every folder that is a git repository on invocation dir
	for name in projects:
		if os.path.isdir(name) and ".git" in os.listdir(name):
			# Skip project if retrying but nothing to do
			if rconfig["retry"] and name not in config:
				continue
			os.chdir(name)
			# Retrieve custom configuration for project
			pconfig = config.get(name, {})
			# Add missing keys from defconfig if not retrying, where we always disable
			for entry in rconfig:
				if rconfig["retry"] and entry not in ["tasks", "keystore", "keyalias", "deploy"]:
					pconfig[entry] = pconfig.get(entry, False)
				elif entry == "force":
					pconfig["force"] = name in rconfig["force"]
				else:
					pconfig[entry] = pconfig.get(entry, rconfig[entry])
			# Empty vessel for the retryable config
			failed[name] = {}
			# Open logfile to store all the output
			with open("log.txt", "w+") as logfile:
				# Introduce the project
				project.presentation(name)
				# Sync the project
				changed = False
				if pconfig["fetch"]:
					pull, changed = project.sync(pconfig["preserve"], logfile)
					# Remember we need to attempt syncing again
					if pull == 1:
						fconfig["fetch"] = (pull == 1)
				# Only attempt gradle projects with build enabled and are either forced or have new changes
				built = False
				if pconfig["build"] and (changed or pconfig["force"]):
					built, tasks = project.build(command, pconfig["tasks"], logfile)
					# Remember if we need to attempt some tasks again
					if not built:
						failed[name]["build"] = True
						failed[name]["force"] = True
						failed[name]["tasks"] = tasks
				# We search for apks to sign and merge them to the current list
				apks = []
				if built or pconfig.get("resign", False):
					signinfo = keystores.get(pconfig["keystore"], {})
					alias = pconfig["keyalias"]
					if signinfo["used"] and signinfo["aliases"][alias]["used"]:
						apks, resign = project.sign(name, workdir, signinfo, alias, logfile)
						if resign:
							failed[name]["resign"] = True
				# We deploy if we built something
				deploylist = pconfig.get("deploylist", {})
				for apk in apks:
					deploylist[apk] = pconfig["deploy"]
				if len(deploylist) > 0:
					faileddeploylist = project.deploy(deploylist, workdir, logfile)
					if len(faileddeploylist) > 0:
						failed[name]["deploylist"] = faileddeploylist
			# If retriable config is empty, drop it
			if len(failed[name]) < 1:
				failed.pop(name)
			# Go back to the invocation directory before moving onto the next project
			os.chdir(workdir)
	# Save the report to file
	with open(".last-syncall", "w") as file:
		json.dump(failed, file)
