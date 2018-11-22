#!/usr/bin/env python3
import os
import sys
import platform
import subprocess
import getpass
import glob
import re
import pickle
# Initialize basic variables
clean = False
fetch = True
build = False
retry = False
force = False
command = "gradlew"
updated = {}
failed = {}
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
		changed = False
		os.chdir(project)
		# Retrieve and show basic information about the project
		log = subprocess.Popen(["git", "log", "-n", "1", "--format=%cr"], stdout = subprocess.PIPE)
		lastdate = log.communicate()[0].decode('ascii').strip()
		print("------------------------------------------")
		print(project + " - last updated " + lastdate)
		# If we disable fetching we do not try to pull anything
		if fetch:
			# Always clean local changes beforehand
			subprocess.Popen(["git", "checkout", "."])
			# Pull changes and save output and return code of the command for checks
			pull = subprocess.Popen(["git", "pull"], stdout = subprocess.PIPE)
			output, code = pull.communicate()[0].decode('ascii'), pull.returncode
			# If something changed flag it for later checks
			if code == 0 and "Already up" not in output:
				changed = True
			print(output)
		# Project may not support building with gradle to check beforehand
		if command in os.listdir("."):
			# Clean task
			if clean:
				print("CLEANING GRADLE CACHE")
				subprocess.call(["./" + command, "clean"])
			# Build task (only if something changed, we are re-trying or we are forcing)
			if build and (changed or (retry and project in rebuild) or (force and project in forced)):
				print("BUILDING GRADLE APP")
				# Initialize clean list to store finished .apks
				releases = []
				# Retrieve the list of tasks for the current project
				try:
					with open(".custom-tasks", "r") as file:
						tasks = file.read().splitlines()
				# Default to a basic release task if none is provided
				except FileNotFoundError:
					tasks = ["assembleRelease"]
				# We store the failed tasks here
				broken = []
				for task in tasks:
					# Assemble a basic unsigned release apk
					assemble = subprocess.call(["./" + command, task])
					# If assembling fails we store the project name for future tasks
					if assemble != 0:
						broken.append(task)
				if len(broken) > 0:
					failed[project] = broken
				# Retrieve all present .apk inside projects folder
				apks = glob.glob("**/*.apk", recursive = True)
				# Filter out those that are not result of the previous build
				regex = re.compile(".*build/outputs/apk/*")
				apks = list(filter(regex.match, apks))
				# Loop through the remaining apks (there may be different flavours)
				for apk in apks:
					# Zipalign for memory optimizations
					align = subprocess.call(["zipalign", "-f", "4", apk, "aligned.apk"])
					if align == 0:
						# Delete the file to avoid re-running over old versions in the future
						os.remove(apk)
						# Build the final .apk name
						name = project
						# A path with a length of 3 means we have flavour names so we append them
						apk = re.sub(regex, "", apk)
						apk = apk.split("/")
						if len(apk) == 3:
							name += "-" + apk[0]
						name += ".apk"
						# Sign the .apk with the provided key
						sign = subprocess.Popen(["apksigner", "sign", "--ks", keystore, "--out", "../SYNCALL-RELEASES/" + name, "aligned.apk"], stdin=subprocess.PIPE)
						# Pipe the password into the signer standard input
						sign.communicate(input=password.encode())
						if sign.returncode == 0:
							# If everything went fine add the new .apk to the list of releases
							releases.append(name)
				# If we at least have a release we add the project to the updated list
				if len(releases) > 0:
					updated[project] = releases
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
