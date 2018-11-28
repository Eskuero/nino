#!/usr/bin/env python3
import os
import sys
import platform
import getpass
import pickle
from project import sync, sign
try:
	import toml
# If the module is not avalaible start a blank config file
except ModuleNotFoundError:
	print("The toml module is required to parse configuration files. Run 'pip install toml'")
	config = {}
else:
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
	"clean": "",
	"fetch": "",
	"preserve": "",
	"build": "",
	"retry": "",
	"force": ""
}
# Initialize running config with falling back values
defconfig = config.get("default", {})
rconfig["clean"] = defconfig.get("clean", False)
rconfig["fetch"] = defconfig.get("fetch", True)
rconfig["preserve"] = defconfig.get("preserve", False)
rconfig["build"] = defconfig.get("build", False)
rconfig["retry"] = defconfig.get("retry", False)
rconfig["force"] = False
# This dictionary will contain the keystore/password used for each projects, plus the default for all of them
keystores = {
	"default": {
		"path": "key.jks",
		"password": ""
		}
}
# Retrieve and store keystores from config file
for project in config:
	path = config[project].get("keystore", False)
	# Only if there was one defined
	if path:
		keystores[project] = {"path": "", "password": ""}
		keystores[project]["path"] = path
# Basic lists of produced outputs, failed, forced of projects
releases = []
failed = []
forced = []
# On Windows the gradle script is written in batch so we append proper extension
command = "gradlew"
if "Windows" in platform.system():
	command += ".bat"
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
			else:
				# In the case of build/force we save a keystore/list respectively
				if name == "build":
					rconfig["build"] = True
					keystores["default"] = value
				elif name == "force":
					rconfig["force"] = True
					forced = value.split(",")
				else:
					print("The argument " + arg[0] + " is expected boolean (y|n). Received: " + value)
					exit(1)
# Confirm we got an existant keystore and force
for project in keystores:
	if config[project].get("build", rconfig["build"]):
		# If we building the project but there's no key, stop
		if keystores[project]["path"]:
			# Make sure the specified file exists
			if not os.path.isfile(keystores[project]["path"]):
				print("The specified keystore for " + project + " does not exist: " + keystores[project]["path"])
				sys.exit(1)
			else:
				# Make sure we save the full path
				keystores[project]["path"] = os.path.abspath(keystores[project]["path"])
				# FIXME: We assume the keystore includes a single key protected with the same password
				keystores[project]["password"] = getpass.getpass("Provide password for " + project + " keystore ("+ keystores[project]["path"] + "): ")
		else:
			print("No keystore was provided for " + project)
			sys.exit(1)
if (rconfig["retry"] or rconfig["force"]) and not rconfig["build"]:
	print("Retrying and forcing require a keystore provided with the --build argument")
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
projects = os.listdir(".")
# Loop for every folder that is a git repository on invocation dir
for project in projects:
	if os.path.isdir(project) and ".git" in os.listdir(project):
		# Clone running config into a project config for this specific one
		pconfig = dict(rconfig)
		# Retrieve custom configuration for project
		cconfig = config.get(project, {})
		# Overwrite configuration with custom values
		pconfig["clean"] = cconfig.get("clean", rconfig["clean"])
		pconfig["fetch"] = cconfig.get("fetch", rconfig["fetch"])
		pconfig["preserve"] = cconfig.get("preserve", rconfig["preserve"])
		pconfig["build"] = cconfig.get("build", rconfig["build"])
		# In case of forcing we ignore custom config if command line options have been received
		if rconfig["force"] and project in forced:
			pconfig["force"] = True
		else:
			pconfig["force"] = cconfig.get("force", False)
		# Get tasks defined on custom config or fallback to basic assembling of a release
		tasks = cconfig.get("tasks", ["assembleRelease"])
		# Attempt to sync and build the project
		result = sync(project, command, pconfig, tasks, pconfig["retry"], rebuild)
		# If something went wrong we record it for reporting
		if result == 1:
			failed.append(project)
		# Else we search for apks to sign and merge them to the current list
		elif result == 0:
			signinfo = keystores.get(project, {})
			keystore = signinfo.get("path", keystores["default"]["path"])
			password = signinfo.get("password", keystores["default"]["password"])
			releases += sign(project, keystore, password)
		# Go back to the invocation directory before moving onto the next project
		os.chdir("..")
# Do not care about failed or successful builds if we are just syncing
if rconfig["build"]:
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
