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
	# Check everything is in place before even starting to retrieve information
	utils.dpnds()

	# We store the running config on a dictionary for ease on accesing the data
	rconfig = {
		"fetch": False,
		"preserve": False,
		"build": False,
		"force": [],
		"tasks": ["assembleRelease"],
		"retry": False,
		"keystore": False,
		"keyalias": False,
		"deploy": [],
	}

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
	else:
		# Retrieve configuration file and load options
		config = utils.cfgfile(rconfig)

	# This dictionary will contain the keystore/password used for each projects, plus the default for all of them
	keystores = config.get("keystores", {})
	# Parse command line arguments and modify running config accordingly
	utils.cmdargs(sys.argv, rconfig, keystores) if not rconfig["retry"] else None

	# Store the dictionary so a retry attempt will use the same keystores
	failed = {"keystores": copy.deepcopy(keystores)}
	# Enable the keystores and keys that will be used
	signing.enable(config, projects, keystores, rconfig)
	# For the enabled projects prompt and store passwords
	signing.secrets(keystores)

	# Loop for every folder on invocation dir
	for name in [name for name in projects if os.path.isdir(name) and name != "SYNCALL-RELEASES"]:
		# Skip project if retrying but nothing to do
		if rconfig["retry"] and name not in config:
			continue
		os.chdir(name)
		# Retrieve custom configuration for project
		pconfig = config.get(name, {})
		# Initialize project class falling back to running config
		app = project(name, rconfig, pconfig, keystores)
		# Vessel for the retryable config, must always retain some configuration
		failed[name] = {}
		# Introduce the project
		app.presentation()
		# Sync the project
		changed = False
		if app.fetch:
			pull, changed = app.sync()
			# Remember we need to attempt syncing again
			if pull == 1:
				failed[name].update({"fetch": None, "preserve": None, "build": None, "force": None, "tasks": None, "keystore": None, "keyalias": None, "resign": None, "deploylist": None, "deploy": None})
		# Only attempt gradle projects with build enabled and are either forced or have new changes
		built = False
		if app.build and (changed or app.force):
			built, app.tasks = app.package(command)
			# Remember if we need to attempt some tasks again
			if not built:
				# Update tasks to only retry remaining, ensure we force rebuild
				app.force = True
				failed[name].update({"build": None, "force": None, "tasks": None, "keystore": None, "keyalias": None, "resign": None, "deploylist": None, "deploy": None})
		# We search for apks to sign and merge them to the current list
		apks = []
		if built or app.resign:
			apks, app.resign = app.sign(workdir)
			if app.resign:
				failed[name].update({"keystore": None, "keyalias": None, "resign": None, "deploylist": None, "deploy": None})
		# We deploy if we built something
		for apk in apks:
			app.deploylist[apk] = app.deploy
		if len(app.deploylist) > 0:
			app.deploylist = app.install(workdir)
			if len(app.deploylist) > 0:
				failed[name].update({"deploylist": None, "deploy": None})
		# Append pending tasks
		for entry in failed[name]:
			failed[name][entry] = getattr(app, entry)
		# If retriable config is empty, drop it
		if not failed[name]:
			failed.pop(name)
		# Go back to the invocation directory before moving onto the next project
		os.chdir(workdir)
	# Save the report to file
	with open(".last-syncall", "w") as file:
		json.dump(failed, file)
