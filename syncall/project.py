#!/usr/bin/env python3
import os
import glob
import re
import subprocess
from .statics import statics

class project():
	def presentation(program, name):
		# Retrieve and show basic information about the project
		if program == 1:
			lastdate = "age unknown"
		else:
			log = subprocess.Popen(program["lastdate"], stdout = subprocess.PIPE)
			lastdate = log.communicate()[0].decode('ascii').strip()
		print("------------------------------------------")
		print(name + " - last updated " + lastdate)

	def getfetchmethod():
		localdir = os.listdir()
		# Check every predefined method to see what's usable
		for method in statics.fetchmethods:
			if method in localdir:
				return statics.fetchmethods[method]
		# Returning after the loop ended means no method is feasible
		return 1

	def sync(program, preserve, logfile):
		print("SYNCING SOURCE CODE ", end = "", flush = True)
		print("SYNCING SOURCE CODE", file = logfile, flush = True)
		# If no program is usable, report and return
		if program == 1:
			print("- \033[93mFETCH METHOD NOT FOUND\033[0m")
			return 1, False
		# Store the current local diff to restore it later
		if preserve:
			diff = subprocess.Popen(program["diff"], stdout = subprocess.PIPE).communicate()[0];
		# Always clean local changes beforehand
		subprocess.call(program["clean"], stdout = logfile, stderr = subprocess.STDOUT)
		# Get changes and save output/return code of the command for checks
		pull = subprocess.call(program["pull"], stdout = logfile, stderr = subprocess.STDOUT)
		# Certain VCS (like mercurial) split syncing into pulling and updating so if a command is specified we need to execute it
		if program["update"]:
			pull = subprocess.call(program["update"], stdout = logfile, stderr = subprocess.STDOUT)
		# We need to pull back to the start of the file to be able to read anything
		logfile.seek(0)
		# If something changed flag it for later checks
		changed = False
		if pull == 0:
			if program["nonews"] not in logfile.read():
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
			apply = subprocess.Popen(program["apply"], stdout = logfile, stderr = subprocess.STDOUT, stdin=subprocess.PIPE)
			apply.communicate(input=diff)
			if apply.returncode == 0:
				print("- \033[92mSUCCESSFUL\033[0m")
			else:
				print("- \033[91mFAILED\033[0m")
		return pull, changed

	def build(command, entrypoint, tasks, logfile):
		# Check if gradle wrapper exists before falling back to system-wide gradle
		if not os.path.isfile(command):
			command = "gradle"
		# User may provide an entrypoint that must be used as setup script before building
		if entrypoint:
			print("RUNNING SETUP SCRIPT ", end = "", flush = True)
			print("\nRUNNING SETUP SCRIPT ", file = logfile, flush = True)
			# Attempt to do the setup
			setup = subprocess.call(["./entrypoint-syncall"], stdout = logfile, stderr = subprocess.STDOUT)
			if setup != 0:
				print("- \033[91mFAILED\033[0m")
				return False, tasks
			else:
				entrypoint = False
				print("- \033[92mSUCCESSFUL\033[0m")
		for task in tasks:
			print("RUNNING GRADLE TASK: " + task + " ", end = "", flush = True)
			print("\nRUNNING GRADLE TASK: " + task, file = logfile, flush = True)
			# Attempt the task, we also redirect stderr to stdout to effectively merge them.
			assemble = subprocess.call([command, "--no-daemon", task], stdout = logfile, stderr = subprocess.STDOUT)
			# If assembling fails we return to tell main
			if assemble != 0:
				print("- \033[91mFAILED\033[0m")
				# Return a list consisting of the failed task and the ones that would have follow
				return False, [word for word in tasks if tasks.index(word) >= tasks.index(task)]
			else:
				print("- \033[92mSUCCESSFUL\033[0m")
		# Arriving here means no task failed
		return True, []

	def sign(name, workdir, signinfo, alias, logfile):
		releases = []
		# Retrieve all present .apk inside projects folder
		apks = glob.glob("**/*.apk", recursive = True)
		# Filter out those that are not result of the previous build
		regex = re.compile(".*build/outputs/apk/*")
		apks = list(filter(regex.match, apks))
		# To tell main if we need to attempt signing again on retry
		resign = False
		# Loop through the remaining apks (there may be different flavours)
		for apk in apks:
			displayname = re.sub(regex, "", apk)
			print("SIGNING OUTPUT: " + displayname + " ", end = "", flush = True)
			print("\nSIGNING OUTPUT: " + displayname, file = logfile, flush = True)
			# A path with a length of 3 means we have flavour names so we append them
			displayname = displayname.split("/")
			if len(displayname) == 3:
				displayname = name + "-" + displayname[0] + ".apk"
			else:
				displayname = name + ".apk"
			# Verify whether is needed or not to sign, as some outputs may come out of building process already signed
			verify = subprocess.call(["apksigner", "verify", apk], stdout = logfile, stdin=subprocess.PIPE, stderr=subprocess.STDOUT)
			if verify == 1:
				# Sign the .apk with the provided key
				sign = subprocess.Popen(["apksigner", "sign", "--ks", signinfo["path"], "--ks-key-alias", alias,"--out", workdir + "/SYNCALL-RELEASES/" + displayname, "--in", apk], stdout = logfile, stdin=subprocess.PIPE, stderr=subprocess.STDOUT)
				# Generate the input using the two passwords and feed it to the subprocess
				secrets = signinfo["password"] + "\n" + signinfo["aliases"][alias]["password"]
				sign.communicate(input=secrets.encode())
				if sign.returncode == 0:
					# If everything went fine add the new .apk to the list of releases
					releases.append(displayname)
					os.remove(apk)
					print("- \033[92mSUCCESSFUL\033[0m")
				else:
					resign = True
					print("- \033[91mFAILED\033[0m")
			else:
				releases.append(displayname)
				os.rename(apk, workdir + "/SYNCALL-RELEASES/" + displayname)
				print("- \033[93mUNNEEDED\033[0m")
		return releases, resign

	def deploy(deploylist, workdir, logfile):
		faileddeploylist = {}
		for apk in deploylist:
			faileddeploylist[apk] = []
			print("DEPLOYING OUTPUT: " + apk)
			for target in deploylist[apk]:
				print("     TO DEVICE: " + target + " ", end = "\r")
				print("\nDEPLOYING OUTPUT " + apk + " TO DEVICE " + target, file = logfile, flush = True)
				try:
					# Make sure the device is online before proceeding, timeout after 15 secs of waiting
					print("     TO DEVICE: " + target + " - \033[93mCONNECTING   \033[0m", end = "\r")
					subprocess.call(["adb", "-s", target, "wait-for-device"], timeout = 15, stdout = logfile, stderr = subprocess.STDOUT)
				# If the adb subprocess timed out we skip this device
				except subprocess.TimeoutExpired:
					faileddeploylist[apk].append(target)
					print("     TO DEVICE: " + target + " - \033[91mNOT REACHABLE\033[0m")
					print("Not reachable", file = logfile, flush = True)
				else:
					print("     TO DEVICE: " + target + " - \033[93mDEPLOYING    \033[0m", end = "\r")
					# We send the apk trying to override it on the system if neccessary
					send = subprocess.call(["adb", "-s" , target, "install", "-r", workdir + "/SYNCALL-RELEASES/" + apk], stdout = logfile, stderr=subprocess.STDOUT)
					if send == 0:
						print("     TO DEVICE: " + target + " - \033[92mSUCCESSFUL   \033[0m")
					else:
						faileddeploylist[apk].append(target)
						print("     TO DEVICE: " + target + " - \033[91mFAILED       \033[0m")
			if len(faileddeploylist[apk]) < 1:
				faileddeploylist.pop(apk)
		return faileddeploylist
