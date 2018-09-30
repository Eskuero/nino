#!/usr/bin/python
import os
import sys
import git
import platform
import subprocess
import getpass
import glob
import re
import datetime
# Initialize basic variables
clean = False
build = False
command = "gradlew"
updated = ""
# If we are on Windows the gradle script is written in batch
if "Windows" in platform.system():
	command += ".bat"
# Check every argument
for i, arg in enumerate(sys.argv):
	# This means we clean gradle cache for the project
	if arg == "--clean":
		clean = True
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
			# And ask for the password
			else:
				# FIXME: We assume the keystore includes a single key protected with the same password
				password = getpass.getpass('Provide the keystore password: ')
# Create the out directory in case it doesn't exist already
if not os.path.isdir("SYNCALL-RELEASES"):
	os.mkdir("SYNCALL-RELEASES")
projects = os.listdir(".")
# Loop for every folder that is a git repository on invocation dir
for project in projects:
	if os.path.isdir(project) and ".git" in os.listdir(project):
		changed = False
		os.chdir(project)
		repo = git.Repo(".").git
		# Retrieve and show basic information about the project
		lastdate = repo.log("-n", "1", "--format=%cr")
		print("------------------------------------------")
		print(project + " - last updated " + lastdate)
		print("------------------------------------------")
		result = repo.pull()
		# If something changed flag it for later checks
		if "Already up" not in result:
			updated += " " + project
			changed = True
		print(result + "\n")
		# Project may not support building with gradle to check beforehand
		if command in os.listdir("."):
			# Clean task
			if clean:
				print("CLEANING GRADLE CACHE")
				subprocess.call(["./" + command, "clean"])
			# Build task (only if something changed)
			if build and changed:
				print("BUILDING GRADLE APP")
				# Assemble a basic unsigned release apk
				subprocess.call(["./" + command, "assembleRelease"])
				# Retrieve all present .apk inside projects folder
				apks = glob.glob("**/*.apk", recursive = True)
				# Filter out those that are not result of the previous build
				regex = re.compile(".*build/outputs/apk/*")
				apks = list(filter(regex.match, apks))
				# Loop through the remaining apks (there may be different flavours)
				for apk in apks:
					# Zipalign for memory optimizations
					subprocess.call(["zipalign", "-f", "4", apk, "aligned.apk"])
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
					p = subprocess.Popen(["apksigner", "sign", "--ks", keystore, "--out", "../SYNCALL-RELEASES/" + name, "aligned.apk"], stdin=subprocess.PIPE)
					# Pipe the password into the signer standard input
					p.communicate(input=password.encode())
		# Go back the invocation directory before moving onto the next project
		os.chdir("..")
# Provide information about the projects that have available updates
print("The following projects have updates:" + updated)