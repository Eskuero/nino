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
			print("SYNCING SOURCE CODE ", end = "", flush = True)
			pull = subprocess.Popen(["git", "pull"], stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
			output, code = pull.communicate()[0].decode('ascii'), pull.returncode
			# If something changed flag it for later checks
			if code == 0:
				if "Already up" not in output:
					print("- \033[92mUPDATED\033[0m")
					changed = True
				else:
					print("- \033[93mUNCHANGED\033[0m")
			else:
				print("- \033[91mFAILED\033[0m")
			# If we are preserving we pipe and apply the previous relevant diff again
			if preserve and diff.decode() != "":
				subprocess.Popen(["git", "apply"], stdin=subprocess.PIPE).communicate(input=diff)
		return changed

	def build(command, tasks):
		# Initialize clean list to store finished .apks
		releases = []
		for task in tasks:
			print("RUNNING GRADLE TASK: " + task + " ", end = "", flush = True)
			# Attempt the task, we also redirect stderr to stdout to effectively merge them.
			assemble = subprocess.Popen(["./" + command, task], stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
			output, code = assemble.communicate()[0], assemble.returncode
			# If assembling fails we save the log to a file
			if code != 0:
				print("- \033[91mFAILED\033[0m")
				with open("log.txt", "w") as file:
					file.write(output.decode())
				return 1
			else:
				print("- \033[92mSUCCESSFUL\033[0m")
		# Arriving here means no task failed
		return 0

	def sign(name, workdir, signinfo, alias):
		releases = []
		# Retrieve all present .apk inside projects folder
		apks = glob.glob("**/*.apk", recursive = True)
		# Filter out those that are not result of the previous build
		regex = re.compile(".*build/outputs/apk/*")
		apks = list(filter(regex.match, apks))
		# Loop through the remaining apks (there may be different flavours)
		for apk in apks:
			print("SIGNING OUTPUT: " + re.sub(regex, "", apk) + " ", end = "", flush = True)
			# Zipalign for memory optimizations if the gradle script doesn't automatically align it
			align = subprocess.call(["zipalign", "-c", "4", apk])
			if align == 0:
				os.rename(apk, "aligned.apk")
			else:
				align = subprocess.call(["zipalign", "-f", "4", apk, "aligned.apk"])
				# Delete the file to avoid re-running over old versions in the future
				os.remove(apk)
			if align == 0:
				# A path with a length of 3 means we have flavour names so we append them
				apk = re.sub(regex, "", apk)
				apk = apk.split("/")
				if len(apk) == 3:
					apk = name + "-" + apk[0] + ".apk"
				else:
					apk = name + ".apk"
				# Sign the .apk with the provided key
				sign = subprocess.Popen(["apksigner", "sign", "--ks", signinfo["path"], "--ks-key-alias", alias,"--out", workdir + "/SYNCALL-RELEASES/" + apk, "--in", "aligned.apk"], stdout = subprocess.DEVNULL, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
				# Generate the input using the two passwords and feed it to the subprocess
				secrets = signinfo["password"] + "\n" + signinfo["aliases"][alias]["password"]
				sign.communicate(input=secrets.encode())
				if sign.returncode == 0:
					# If everything went fine add the new .apk to the list of releases
					releases.append(apk)
					print("- \033[92mSUCCESSFUL\033[0m")
				else:
					print("- \033[91mFAILED\033[0m")
			else:
				print("- \033[91mFAILED\033[0m")
		return releases

	def deploy(apks, targets, workdir):
		for apk in apks:
			print("DEPLOYING OUTPUT: " + apk)
			for target in targets:
				print("     TO DEVICE: " + target + " ", end = "\r")
				try:
					# Make sure the device is online before proceeding, timeout after 15 secs of waiting
					print("     TO DEVICE: " + target + " - \033[93mCONNECTING   \033[0m", end = "\r")
					subprocess.run(["adb", "-s", target, "wait-for-device"], timeout = 15, stdout = subprocess.DEVNULL, stderr=subprocess.DEVNULL)
				# If the adb subprocess timed out we skip this device
				except subprocess.TimeoutExpired:
					print("     TO DEVICE: " + target + " - \033[91mNOT REACHABLE\033[0m")
				else:
					print("     TO DEVICE: " + target + " - \033[93mDEPLOYING    \033[0m", end = "\r")
					# We send the apk trying to override it on the system if neccessary
					send = subprocess.Popen(["adb", "-s" , target, "install", "-r", workdir + "/SYNCALL-RELEASES/" + apk], stdout = subprocess.DEVNULL, stderr=subprocess.DEVNULL)
					send.communicate()
					if send.returncode == 0:
						print("     TO DEVICE: " + target + " - \033[92mSUCCESSFUL   \033[0m")
					else:
						print("     TO DEVICE: " + target + " - \033[91mFAILED       \033[0m")
