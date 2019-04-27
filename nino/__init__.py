import os
import sys
import json
import colorama
from .project import project
from .signing import signing
from .utils import utils
from .statics import statics

def main():
	# Start colorama for ANSI escape codes under Windows
	colorama.init()

	# Check everything is in place before even starting to retrieve information
	utils.dpnds()

	# We store the configuration on a dictionary for ease on accesing the data
	config = {
		"default": {
			"sync": False,
			"preserve": False,
			"build": False,
			"force": [],
			"tasks": ["assembleRelease"],
			"keystore": False,
			"keyalias": False,
			"deploy": [],
		}
	}

	# Create the out directory in case it doesn't exist already
	if not os.path.isdir("NINO-RELEASES"):
		os.mkdir("NINO-RELEASES")
	# Retryable config that will be dumped onto .nino-last
	failed = {}

	# When retrying we completely ignore configurations from file and cmdargs
	if not ({"-r", "--retry"}).isdisjoint(set(sys.argv)):
		try:
			with open(".nino-last", "r") as file:
				fileconfig = json.load(file)
		except:
			print("Failed to load retryable config from .nino-last so can't proceed")
			sys.exit(1)
		else:
			retry = True
	else:
		retry = False
		# Retrieve configuration file and load options
		fileconfig = utils.cfgfile()
	# Update or append each project specifications to the config
	for entry in fileconfig:
		try:
			config[entry].update(fileconfig[entry])
		except KeyError:
			config[entry] = fileconfig[entry]

	# Parse command line arguments and modify running config accordingly
	utils.cmdargs(config["default"]) if not retry else None
	# This dictionary will contain the keystore/password used for each projects, plus the default for all of them
	keystores = signing.setup(statics.projects, config)
	# For the enabled projects prompt and store passwords
	signing.secrets(keystores)

	# Loop for every folder on invocation dir
	for name in [name for name in statics.projects if os.path.isdir(name) and name != "NINO-RELEASES"]:
		# Skip project if retrying but nothing to do
		if retry and name not in config:
			continue
		os.chdir(name)
		# Retrieve custom configuration for project
		pconfig = config.get(name, {})
		# Initialize project class falling back to running config
		app = project(name, config["default"], pconfig, keystores, retry)
		# Introduce the project
		app.presentation()
		# Sync the project
		if app.sync:
			app.fetch()
		# Only attempt gradle projects with build enabled and are either forced or have new changes
		if app.build and (app.changed or app.force):
			app.package()
		# We search for apks to sign and merge them to the current list
		if app.built == 0 or app.resign:
			app.sign()
		# We deploy if we built something
		if app.deploylist:
			app.install()
		# Store retriable config for project if not empty
		if app.failed:
			failed[name] = app.failed
		# Go back to the invocation directory before moving onto the next project
		os.chdir(statics.workdir)
	# Save the report to file
	with open(".nino-last", "w") as file:
		json.dump(failed, file)
