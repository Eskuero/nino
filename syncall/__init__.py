#!/usr/bin/env python3
import os
import sys
import copy
import platform
import json
from .project import project
from .signing import signing
from .utils import utils

def main():
	# We store the running config on a dictionary for ease on accesing the data
	rconfig = {
		"fetch": False,
		"preserve": False,
		"build": False,
		"force": [],
		"entrypoint": False,
		"tasks": ["assembleRelease"],
		"retry": False,
		"resign": False,
		"keystore": False,
		"keyalias": False,
		"deploy": [],
		"deploylist": {}
	}

	# This dictionary will contain the keystore/password used for each projects, plus the default for all of them
	keystores = {}
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

	# When retrying we completely ignore configurations from file and cmdargs
	if "--retry=y" in sys.argv:
		config = {}
		try:
			with open(".last-syncall", "r") as file:
				config = json.load(file)
		except FileNotFoundError:
			pass
		rconfig["retry"] = True
		keystores = config.get("keystores", {})
	else:
		# Retrieve configuration file and load options
		config = utils.cfgfile(rconfig)
		keystores = config.get("keystores", {})
		# Parse command line arguments and modify running config accordingly
		utils.cmdargs(sys.argv, rconfig, keystores)

	# Store the dictionary so a retry attempt will use the same keystores
	failed = {"keystores": copy.deepcopy(keystores)}
	# Enable the keystores and keys that will be used
	signing.enable(config, projects, keystores, rconfig)
	# For the enabled projects prompt and store passwords
	signing.secrets(keystores)

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
				# defconfig force is a list we must check and convert to boolean
				if entry == "force":
					pconfig["force"] = pconfig.get("force", name in rconfig["force"])
				else:
					pconfig[entry] = copy.deepcopy(pconfig.get(entry, rconfig[entry]))
			# Vessel for the retryable config, must always retain some configuration
			failed[name] = {}
			# If some steps fail even if the following run fine those previous may provide more work in a retry, so we register them again to check
			pending = []
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
						pending = set(pending).union(set(["fetch", "preserve", "build", "force", "entrypoint", "tasks", "keystore", "keyalias", "resign", "deploylist", "deploy"]))
				# Only attempt gradle projects with build enabled and are either forced or have new changes
				built = False
				if pconfig["build"] and (changed or pconfig["force"]):
					built, tasks = project.build(command, pconfig["entrypoint"], pconfig["tasks"], logfile)
					# Remember if we need to attempt some tasks again
					if not built:
						# Update tasks to only retry remaining, ensure we force rebuild
						pconfig["force"] = True
						pconfig["tasks"] = tasks
						pending = set(pending).union(set(["build", "force", "entrypoint", "tasks", "keystore", "keyalias", "resign", "deploylist", "deploy"]))
				# We search for apks to sign and merge them to the current list
				apks = []
				if built or pconfig["resign"]:
					signinfo = keystores.get(pconfig["keystore"], {})
					alias = pconfig["keyalias"]
					if signinfo["used"] and signinfo["aliases"][alias]["used"]:
						apks, resign = project.sign(name, workdir, signinfo, alias, logfile)
						if resign:
							pconfig["resign"] = True
							pending = set(pending).union(set(["keystore", "keyalias", "resign", "deploylist", "deploy"]))
				# We deploy if we built something
				for apk in apks:
					pconfig["deploylist"][apk] = pconfig["deploy"]
				if len(pconfig["deploylist"]) > 0:
					pconfig["deploylist"] = project.deploy(pconfig["deploylist"], workdir, logfile)
					if len(pconfig["deploylist"]) > 0:
						pending = set(pending).union(set(["deploylist", "deploy"]))
			# Append pending tasks
			for entry in pending:
				failed[name][entry] = pconfig[entry]
			# If retriable config is empty, drop it
			if len(failed[name]) < 1:
				failed.pop(name)
			# Go back to the invocation directory before moving onto the next project
			os.chdir(workdir)
	# Save the report to file
	with open(".last-syncall", "w") as file:
		json.dump(failed, file)
