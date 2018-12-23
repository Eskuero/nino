#!/usr/bin/env python3
import os
import sys
import platform
import getpass
import pickle
import subprocess
import toml
from .project import project

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
	rconfig["force"] = False

	# This dictionary will contain the keystore/password used for each projects, plus the default for all of them
	keystores = config.get("keystores", {})

	# Basic lists of produced outputs, failed, forced of projects and avalaible folders
	releases = []
	failed = []
	forced = []
	projects = os.listdir()
	workdir = os.getcwd()

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
				if value == "y":
					rconfig[name] = True
				elif value == "n":
					rconfig[name] = False
					if name == "build":
						keystores["default"]["used"] = False
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
					elif name == "force":
						rconfig["force"] = True
						forced = value.split(",")
					else:
						print("The argument " + arg[0] + " is expected boolean (y|n). Received: " + value)
						sys.exit(1)

	# Enable custom keystores defined for each project
	for name in config:
		if not name == "keystores" and (name in projects or (name == "default" and "overridestore" not in keystores)):
			# Retrieve the path only if building, either from default or custom
			if config[name].get("build", rconfig["build"]):
				store = config[name].get("keystore", rconfig["keystore"])
				alias = config[name].get("keyalias", rconfig["keyalias"])
				# Only if path is defined and in use
				if store and alias:
					if alias in keystores.get(store, {}).get("aliases", {}):
						keystores[store]["used"] = True
						keystores[store]["aliases"][alias]["used"] = True
					else:
						print("The specified keystore/key alias combination for " + name + " doesn't exist on configuration file")
						sys.exit(1)
				else:
					print(name + " build is enabled but lacks an assigned keystore and/or key.")
					sys.exit(1)

	# On Windows the gradle script is written in batch so we append proper extension
	command = "gradlew"
	if "Windows" in platform.system():
		command += ".bat"
	# Confirm we got an existant keystore and force
	for store in keystores:
		# If the keystore won't be used we skip it altogether
		if keystores[store].get("used", False):
			# Make sure the specified path for the keystore exists
			path = keystores[store].get("path", "")
			if not os.path.isfile(path):
				print("The specified path for " + store + " keystore does not exist: '" + path + "'")
				sys.exit(1)
			else:
				# Make sure we save the full path
				keystores[store]["path"] = os.path.abspath(keystores[store]["path"])
				# Ask for the keystore password
				try:
					keystores[store]["password"]
				except KeyError:
					keystores[store]["password"] = getpass.getpass("Enter password of '" + store + "' keystore '"+ keystores[store]["path"] + "': ")
				# Try to retrieve aliases from the keystore to test password
				aliases = keystores[store].get("aliases", {})
				for alias in (alias for alias in aliases if keystores[store]["aliases"][alias].get("used", False)):
					listing = subprocess.Popen(["keytool", "-list", "-keystore", keystores[store]["path"], "-alias", alias], stdout = subprocess.DEVNULL, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
					listing.communicate(input=keystores[store]["password"].encode())
					if listing.returncode != 0:
						print("Keystore password is incorrect or alias '" + alias + "' does not exist on keystore")
						sys.exit(1)
					else:
						# Ask for the key password
						try:
							keystores[store]["aliases"][alias]["password"]
						except KeyError:
							keystores[store]["aliases"][alias]["password"] = getpass.getpass("     Enter password for key '" + alias + "' of '" + store + "' keystore '"+ keystores[store]["path"] + "': ")
						# Attempt to export to a temporal keystore to test the alias password
						testkey = subprocess.Popen(["keytool", "-importkeystore", "-srckeystore", keystores[store]["path"], "-destkeystore", "tmpstore", "-deststorepass", "tmpstore", "-srcalias", alias],  stdout = subprocess.DEVNULL, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
						# Generate the input using the two passwords and feed it to the subprocess
						secrets = keystores[store]["password"] + "\n" + keystores[store]["aliases"][alias]["password"]
						testkey.communicate(input=secrets.encode())
						if testkey.returncode == 0:
							# Everything was fine, delete the temporal keystore
							os.remove("tmpstore")
						else:
							print("Provided password for key '" + alias + "' of keystore '" + keystores[store]["path"] +"' is incorrect")
							sys.exit(1)

	# Create the out directory in case it doesn't exist already
	if rconfig["build"] and not os.path.isdir("SYNCALL-RELEASES"):
		os.mkdir("SYNCALL-RELEASES")
	# Retrieve list of the previously failed to build projects
	try:
		with open(".retry-projects", "rb") as file:
			rebuild = pickle.load(file)
	# Restart the list if no previous file is found
	except FileNotFoundError:
		rebuild = []

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
			if rconfig["force"] and name in forced:
				force = True
			else:
				force = cconfig.get("force", False)
			# Get tasks defined on custom config or fallback to basic assembling of a release
			tasks = cconfig.get("tasks", ["assembleRelease"])
			# Sync the project
			changed = project.sync(name, fetch, preserve)
			# Only attempt gradle projects with build enabled and are either forced, retrying or have new changes
			if command in os.listdir() and build and (changed or (rconfig["retry"] and name in rebuild) or force):
				result = project.build(command, tasks)
				# If some task went wrong we report it
				if result == 1:
					failed.append(name)
				# Else we search for apks to sign and merge them to the current list
				elif result == 0:
					signinfo = keystores.get(cconfig.get("keystore", rconfig["keystore"]), {})
					alias = cconfig.get("keyalias", rconfig["keyalias"])
					if signinfo["used"] and signinfo["aliases"][alias]["used"]:
						releases += project.sign(name, workdir, signinfo, alias)
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
