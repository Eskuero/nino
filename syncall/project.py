#!/usr/bin/env python3
import os
import glob
import re
import subprocess

class project():
	def sync(name, fetch, preserve, logfile):
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
			print("SYNCING SOURCE CODE", file = logfile, flush = True)
			pull = subprocess.call(["git", "pull"], stdout = logfile, stderr = subprocess.STDOUT)
			# We need to pull back to the start of the file to be able to read anything
			logfile.seek(0)
			# If something changed flag it for later checks
			if pull == 0:
				if "Already up" not in logfile.read():
					print("- \033[92mUPDATED\033[0m")
					changed = True
				else:
					print("- \033[93mUNCHANGED\033[0m")
			else:
				print("- \033[91mFAILED\033[0m")
			# If we are preserving we pipe and apply the previous relevant diff again
			if preserve and diff.decode() != "":
				print("     PRESERVING LOCAL CHANGES ", end = "", flush = True)
				print("\nPRESERVING LOCAL CHANGES\n" + diff.decode(), file = logfile, flush = True)
				apply = subprocess.Popen(["git", "apply"], stdout = logfile, stderr = subprocess.STDOUT, stdin=subprocess.PIPE)
				apply.communicate(input=diff)
				if apply.returncode == 0:
					print("- \033[92mSUCCESSFUL\033[0m")
				else:
					print("- \033[91mFAILED\033[0m")
		return changed

	def build(command, tasks, logfile):
		# Initialize clean list to store finished .apks
		releases = []
		for task in tasks:
			print("RUNNING GRADLE TASK: " + task + " ", end = "", flush = True)
			print("\nRUNNING GRADLE TASK: " + task, file = logfile, flush = True)
			# Attempt the task, we also redirect stderr to stdout to effectively merge them.
			assemble = subprocess.call(["./" + command, task], stdout = logfile, stderr = subprocess.STDOUT)
			# If assembling fails we return to tell main
			if assemble != 0:
				print("- \033[91mFAILED\033[0m")
				return 1
			else:
				print("- \033[92mSUCCESSFUL\033[0m")
		# Arriving here means no task failed
		return 0

	def sign(name, workdir, signinfo, alias, logfile):
		releases = []
		# Retrieve all present .apk inside projects folder
		apks = glob.glob("**/*.apk", recursive = True)
		# Filter out those that are not result of the previous build
		regex = re.compile(".*build/outputs/apk/*")
		apks = list(filter(regex.match, apks))
		# Loop through the remaining apks (there may be different flavours)
		for apk in apks:
			displayname = re.sub(regex, "", apk)
			print("PREPARING OUTPUT: " + displayname + " ")
			print("\nPREPARING OUTPUT: " + displayname, file = logfile, flush = True)
			# Zipalign for memory optimizations if the gradle script doesn't automatically align it
			print("     ZIPALIGNING ", end = "", flush = True)
			print("     ZIPALIGNING", file = logfile, flush = True)
			align = subprocess.call(["zipalign", "-c", "4", apk], stdout = logfile, stderr=subprocess.STDOUT)
			if align == 0:
				print("- \033[93mUNNEEDED\033[0m")
				os.rename(apk, "aligned.apk")
			else:
				align = subprocess.call(["zipalign", "-f", "4", apk, "aligned.apk"], stdout = logfile, stderr=subprocess.STDOUT)
				if align == 0:
					print("- \033[92mSUCCESSFUL\033[0m")
				else:
					print("- \033[91mFAILED\033[0m")
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
				print("     SIGNING ", end = "", flush = True)
				print("     SIGNING", file = logfile, flush = True)
				# Sign the .apk with the provided key
				sign = subprocess.Popen(["apksigner", "sign", "--ks", signinfo["path"], "--ks-key-alias", alias,"--out", workdir + "/SYNCALL-RELEASES/" + apk, "--in", "aligned.apk"], stdout = logfile, stdin=subprocess.PIPE, stderr=subprocess.STDOUT)
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

	def deploy(apks, targets, workdir, logfile):
		for apk in apks:
			print("DEPLOYING OUTPUT: " + apk)
			for target in targets:
				print("     TO DEVICE: " + target + " ", end = "\r")
				print("\nDEPLOYING OUTPUT " + apk + " TO DEVICE " + target, file = logfile, flush = True)
				try:
					# Make sure the device is online before proceeding, timeout after 15 secs of waiting
					print("     TO DEVICE: " + target + " - \033[93mCONNECTING   \033[0m", end = "\r")
					subprocess.call(["adb", "-s", target, "wait-for-device"], timeout = 15, stdout = logfile, stderr = subprocess.STDOUT)
				# If the adb subprocess timed out we skip this device
				except subprocess.TimeoutExpired:
					print("     TO DEVICE: " + target + " - \033[91mNOT REACHABLE\033[0m")
					print("Not reachable", file = logfile, flush = True)
				else:
					print("     TO DEVICE: " + target + " - \033[93mDEPLOYING    \033[0m", end = "\r")
					# We send the apk trying to override it on the system if neccessary
					send = subprocess.call(["adb", "-s" , target, "install", "-r", workdir + "/SYNCALL-RELEASES/" + apk], stdout = logfile, stderr=subprocess.STDOUT)
					if send == 0:
						print("     TO DEVICE: " + target + " - \033[92mSUCCESSFUL   \033[0m")
					else:
						print("     TO DEVICE: " + target + " - \033[91mFAILED       \033[0m")
