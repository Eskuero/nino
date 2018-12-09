#!/usr/bin/env python3
import os
import glob
import re
import subprocess

class project():
	def sync(name, fetch, preserve):
		changed = False
		# Retrieve and show basic information about the project
		log = subprocess.Popen(["git", "log", "-n", "1", "--format=%cr"], stdout = subprocess.PIPE)
		lastdate = log.communicate()[0].decode('ascii').strip()
		print("------------------------------------------")
		print(name + " - last updated " + lastdate)
		# If we disable fetching we do not try to pull anything
		if fetch:
			# Store the current local diff to restore it later
			if preserve:
				diff = subprocess.Popen(["git", "diff"], stdout = subprocess.PIPE).communicate()[0];
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
			if preserve and diff.decode() != "":
				subprocess.Popen(["git", "apply"], stdin=subprocess.PIPE).communicate(input=diff)
		return changed

	def build(command, tasks):
		# Initialize clean list to store finished .apks
		releases = []
		for task in tasks:
			print("RUNNING GRADLE TASK: " + task)
			# Attempt the task, we also redirect stderr to stdout to effectively merge them.
			assemble = subprocess.Popen(["./" + command, task], stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
			output, code = assemble.communicate()[0], assemble.returncode
			# If assembling fails we save the log to a file
			if code != 0:
				with open("log.txt", "w") as file:
					file.write(output.decode())
				return 1
		# Arriving here means no task failed
		return 0

	def sign(name, workdir, keystore, password):
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
				# A path with a length of 3 means we have flavour names so we append them
				apk = re.sub(regex, "", apk)
				apk = apk.split("/")
				if len(apk) == 3:
					name += "-" + apk[0]
				name += ".apk"
				# Sign the .apk with the provided key
				sign = subprocess.Popen(["apksigner", "sign", "--ks", keystore, "--out", workdir + "/SYNCALL-RELEASES/" + name, "aligned.apk"], stdin=subprocess.PIPE)
				# Pipe the password into the signer standard input
				sign.communicate(input=password.encode())
				if sign.returncode == 0:
					# If everything went fine add the new .apk to the list of releases
					releases.append(name)
		return releases
