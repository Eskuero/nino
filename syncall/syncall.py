#!/usr/bin/env python3
import os
import sys
import platform
import getpass
import pickle
from project import sync, sign
# Initialize basic variables
clean = False
fetch = True
local = False
build = False
retry = False
force = False
keystore = ""
command = "gradlew"
updated = {}
failed = {}
forced = []
rebuild = []
# If we are on Windows the gradle script is written in batch
if "Windows" in platform.system():
	command += ".bat"
# Check every argument
for i, arg in enumerate(sys.argv):
	# This means we clean gradle cache for every project
	if arg == "--clean":
		clean = True
	# This means we do not check remote for new changes
	if arg == "--nofetch":
		fetch = False
	# This means we attempt to preserve local changes via diffing
	if arg == "--preserve":
		local = True
	# This means we should build the new changes
	if arg == "--build":
		build = True
		# Build argument expects a keystore file to sign the built .apk
		try:
			keystore = sys.argv[i+1]
		except IndexError:
			print("You must provide a keystore file as the --build argument value for signing the release apks")
			sys.exit(1)
		else:
			# Make sure the specified file exists
			if not os.path.isfile(keystore):
				print("The specified keystore file doesn't exists. Make sure you provided the correct path")
				sys.exit(1)
			else:
				# Make sure we have the full path to the key
				keystore = os.path.abspath(keystore)
				# FIXME: We assume the keystore includes a single key protected with the same password
				password = getpass.getpass('Provide the keystore password: ')
	# This means we try to build the projects that failed in the previous attempt
	if arg == "--retry":
		retry = True
	# This means that we force build of certain projects even if they are neither failed or updated
	if arg == "--force":
		force = True
		try:
			forced = sys.argv[i+1].split(",")
		except IndexError:
			print("You must provide a list of comma joined project names to force rebuild")
			sys.exit(1)
if (retry or force) and not build:
	print("Retrying and forcing require a keystore provided with the --build argument")
	sys.exit(1)
# Create the out directory in case it doesn't exist already
if build and not os.path.isdir("SYNCALL-RELEASES"):
	os.mkdir("SYNCALL-RELEASES")
# Retrieve list of the previously failed to build projects
try:
	with open(".retry-projects", "rb") as file:
		rebuild = pickle.load(file)
# We create an empty file in case it doesn't exists already
except FileNotFoundError:
	with open(".retry-projects", "wb") as file:
		pickle.dump(failed, file)
projects = os.listdir(".")
# Loop for every folder that is a git repository on invocation dir
for project in projects:
	if os.path.isdir(project) and ".git" in os.listdir(project):
		failed = sync(project, command, clean, fetch, local, build, retry, force, forced, rebuild, failed)
		updated = sign(project, keystore, password, updated)
		# Go back the invocation directory before moving onto the next project
		os.chdir("..")
# Do not care about failed or successful builds if we are just syncing
if build:
	# Write to the file which projects have build failures
	with open('.retry-projects', 'wb') as file:
	    pickle.dump(failed, file)
	# Provide information about the projects that have available updates
	for key, value in updated.items():
		print("The project " + key + " built the following files:")
		for file in value:
			print("- " + file)
	# Provide information about which projects had failures
	for key, value in failed.items():
		print("The project " + key + " failed the following tasks:")
		for file in value:
			print("- " + file)
