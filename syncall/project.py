#!/usr/bin/env python3
import os
import glob
import re
import subprocess

def sync(project, command, clean, fetch, local, build, retry, force, forced, rebuild, failed):
	changed = False
	os.chdir(project)
	# Retrieve and show basic information about the project
	log = subprocess.Popen(["git", "log", "-n", "1", "--format=%cr"], stdout = subprocess.PIPE)
	lastdate = log.communicate()[0].decode('ascii').strip()
	print("------------------------------------------")
	print(project + " - last updated " + lastdate)
	# If we disable fetching we do not try to pull anything
	if fetch:
		# Store the current local diff to restore it later
		if local:
			diff = subprocess.Popen(["git", "diff"], stdout = subprocess.PIPE).communicate()[0].decode('ascii');
		# Always clean local changes beforehand
		subprocess.Popen(["git", "checkout", "."])
		# Pull changes and save output and return code of the command for checks
		pull = subprocess.Popen(["git", "pull"], stdout = subprocess.PIPE)
		output, code = pull.communicate()[0].decode('ascii'), pull.returncode
		# If something changed flag it for later checks
		if code == 0 and "Already up" not in output:
			changed = True
		print(output)
		# If we are preserving we pipe and apply the previous relevant diff again
		if local and diff != "":
			subprocess.Popen(["git", "apply"], stdin=subprocess.PIPE).communicate(input=diff.encode())
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
	return failed

def sign(project, keystore, password, updated):
	releases = []
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
	return updated
