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
	rconfig["force"] = False

	# This dictionary will contain the keystore/password used for each projects, plus the default for all of them
	keystores = {
		"default": {
			"path": False,
			"alias": False,
			"storepass": "",
			"aliaspass": "",
			"used": False
		}
	}
	# Initialize keystore if default path is provided
	keystores["default"]["path"] = defconfig.get("keystore", False)
	keystores["default"]["alias"] = defconfig.get("keyalias", False)
	# If we are building by default and path existed we enable usage
	if rconfig["build"] and keystores["default"]["path"] and keystores["default"]["alias"]:
		keystores["default"]["used"] = True

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
						keystores["default"]["path"] = value[0]
						try:
							keystores["default"]["alias"] = value[1]
						except IndexError:
							print("No alias was given for keystore " + value[0] + " provided through command line")
							sys.exit(1)
						keystores["default"]["used"] = True
					elif name == "force":
						rconfig["force"] = True
						forced = value.split(",")
					else:
						print("The argument " + arg[0] + " is expected boolean (y|n). Received: " + value)
						sys.exit(1)
	# Retrieve and store keystores from config file
	for name in config:
		if not name == "default" and name in projects:
			# Retrieve the path only if building, either because default or explicit
			if config[name].get("build", rconfig["build"]):
				path = config[name].get("keystore", False)
				alias = config[name].get("keyalias", False)
				# Only if path is defined and in use
				if path and alias:
					keystores[name] = {
						"path": path,
						"alias": alias,
						"storepass": "",
						"aliaspass": "",
						"used": True
					}
				elif keystores["default"]["path"] and keystores["default"]["alias"]:
					keystores["default"]["used"] = True
				else:
					print(name + " build is enabled but lacks an asigned keystore and/or key.")
					sys.exit(1)

	# On Windows the gradle script is written in batch so we append proper extension
	command = "gradlew"
	if "Windows" in platform.system():
		command += ".bat"
	# Confirm we got an existant keystore and force
	for name in keystores:
		# Only ask for password of default keystore or building projects
		if config.get(name, {}).get("build", rconfig["build"]) and keystores[name]["used"]:
			# There's no key so stop
			if keystores[name]["path"] and keystores[name]["alias"]:
				# Make sure the specified file exists
				if not os.path.isfile(keystores[name]["path"]):
					print("The specified keystore for " + name + " does not exist: " + keystores[name]["path"])
					sys.exit(1)
				else:
					# Make sure we save the full path
					keystores[name]["path"] = os.path.abspath(keystores[name]["path"])
					# Ask for the keystore password
					keystores[name]["storepass"] = getpass.getpass("Enter password of '" + name + "' keystore '"+ keystores[name]["path"] + "': ")
					# Try to retrieve the specified alias from the keystore to test password
					listing = subprocess.Popen(["keytool", "-list", "-keystore", keystores[name]["path"], "-alias", keystores[name]["alias"]], stdout = subprocess.DEVNULL, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
					listing.communicate(input=keystores[name]["storepass"].encode())
					if listing.returncode != 0:
						print("Password is incorrect or the specified alias '" + keystores[name]["alias"] + "' does not exist on keystore")
						sys.exit(1)
					else:
						# Ask for the key password
						keystores[name]["aliaspass"] = getpass.getpass("     Enter password for key '" + keystores[name]["alias"] + "': ")
						# Attempt to export to a temporal keystore to test the alias password
						testkey = subprocess.Popen(["keytool", "-importkeystore", "-srckeystore", keystores[name]["path"], "-destkeystore", "tmpstore", "-deststorepass", "tmpstore", "-srcalias", keystores[name]["alias"]],  stdout = subprocess.DEVNULL, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
						# Generate the input using the two passwords and feed it to the subprocess
						secrets = keystores[name]["storepass"] + "\n" + keystores[name]["aliaspass"]
						testkey.communicate(input=secrets.encode())
						if testkey.returncode == 0:
							# Everything was fine, delete the temporal keystore
							os.remove("tmpstore")
						else:
							print("Provided password for key '" + keystores[name]["alias"] + "' of keystore '" + keystores[name]["path"] +"' is incorrect")
							sys.exit(1)
			else:
				print("No keystore/key name was provided for " + name)
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
					signinfo = keystores.get(name, keystores["default"])
					if signinfo["used"]:
						releases += project.sign(name, workdir, signinfo)
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
