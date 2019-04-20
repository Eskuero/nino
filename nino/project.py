#!/usr/bin/env python3
import os
import glob
import re
import subprocess
from .statics import statics

class project():
	def __init__(self, name, rconfig, pconfig, keystores):
		self.name = name
		# Retrieve value for each property except for force because has different types
		for prop in [prop for prop in rconfig if prop != "force"]:
			setattr(self, prop, pconfig.get(prop, rconfig[prop]))
		# Detect the valid fetching method even when fetching is disabled because is needed on presentation
		self.fetcher = self.getfetchmethod()
		# Forcing stores a list on running config and a bool on project so check both
		self.force = name in rconfig["force"] or pconfig.get("force", False)
		# Retrieve full path and secrets for the specified keystore
		self.signinfo = keystores.get(self.keystore, {})
		# Some properties are only generated by nino in the scope of retrying so avoid user interference
		self.resign = pconfig.get("resign", False) if rconfig["retry"] else False
		self.deploylist = pconfig.get("deploylist", {}) if rconfig["retry"] else {}
		# We need to store the output of every operation to a file
		self.logfile = open("log.txt", "w+")

	def presentation(self):
		# Retrieve and show basic information about the project
		if not self.fetcher:
			lastdate = "age unknown"
		else:
			log = subprocess.Popen(self.fetcher["lastdate"], stdout = subprocess.PIPE)
			lastdate = log.communicate()[0].decode('ascii').strip()
		print("------------------------------------------")
		print(self.name + " - last updated " + lastdate)

	def getfetchmethod(self):
		localdir = os.listdir()
		# Check every predefined method to see what's usable
		for method in statics.fetchmethods:
			if method in localdir:
				return statics.fetchmethods[method]
		# Returning after the loop ended means no method is feasible
		return False

	def fetch(self):
		print("SYNCING SOURCE CODE ", end = "", flush = True)
		print("SYNCING SOURCE CODE", file = self.logfile, flush = True)
		# If no program is usable, report and return
		if not self.fetcher:
			print("- \033[93mFETCH METHOD NOT FOUND\033[0m")
			# Not neccessarily an error to retry
			return 0, False
		# Store the current local diff to restore it later
		if self.preserve:
			diff = subprocess.Popen(self.fetcher["diff"], stdout = subprocess.PIPE).communicate()[0];
		# Always clean local changes beforehand
		subprocess.call(self.fetcher["clean"], stdout = self.logfile, stderr = subprocess.STDOUT)
		# Get changes and save output/return code of the command for checks
		pull = subprocess.call(self.fetcher["pull"], stdout = self.logfile, stderr = subprocess.STDOUT)
		# Certain VCS (like mercurial) split syncing into pulling and updating so if a command is specified we need to execute it
		if self.fetcher["update"]:
			pull = subprocess.call(self.fetcher["update"], stdout = self.logfile, stderr = subprocess.STDOUT)
		# We need to pull back to the start of the file to be able to read anything
		self.logfile.seek(0)
		# If something changed flag it for later checks
		changed = False
		if pull == 0:
			if self.fetcher["nonews"] not in self.logfile.read():
				print("- \033[92mUPDATED\033[0m")
				changed = True
			else:
				print("- \033[93mUNCHANGED\033[0m")
		else:
			print("- \033[91mFAILED\033[0m")
		# If we are preserving we pipe and apply the previous relevant diff again
		if self.preserve and diff.decode() != "":
			print("     PRESERVING LOCAL CHANGES ", end = "", flush = True)
			print("\nPRESERVING LOCAL CHANGES\n" + diff.decode(), file = self.logfile, flush = True)
			apply = subprocess.Popen(self.fetcher["apply"], stdout = self.logfile, stderr = subprocess.STDOUT, stdin=subprocess.PIPE)
			apply.communicate(input=diff)
			if apply.returncode == 0:
				print("- \033[92mSUCCESSFUL\033[0m")
			else:
				print("- \033[91mFAILED\033[0m")
		return pull, changed

	def package(self, command):
		# Check if gradle wrapper exists before falling back to system-wide gradle
		if not os.path.isfile(command):
			command = "gradle"
		# User may provide an entrypoint that must be used as setup script before building
		if os.path.isfile("./nino-entrypoint"):
			print("RUNNING ENTRYPOINT SCRIPT ", end = "", flush = True)
			print("\nRUNNING ENTRYPOINT SCRIPT ", file = self.logfile, flush = True)
			# Attempt to do the setup
			setup = subprocess.call(["./nino-entrypoint"], stdout = self.logfile, stderr = subprocess.STDOUT)
			if setup != 0:
				print("- \033[91mFAILED\033[0m")
				return False, self.tasks
			else:
				print("- \033[92mSUCCESSFUL\033[0m")
		for task in self.tasks:
			print("RUNNING GRADLE TASK: " + task + " ", end = "", flush = True)
			print("\nRUNNING GRADLE TASK: " + task, file = self.logfile, flush = True)
			# Attempt the task, we also redirect stderr to stdout to effectively merge them.
			assemble = subprocess.call([command, "--no-daemon", task], stdout = self.logfile, stderr = subprocess.STDOUT)
			# If assembling fails we return to tell main
			if assemble != 0:
				print("- \033[91mFAILED\033[0m")
				# Return a list consisting of the failed task and the ones that would have follow
				return False, [word for word in self.tasks if self.tasks.index(word) >= self.tasks.index(task)]
			else:
				print("- \033[92mSUCCESSFUL\033[0m")
		# Arriving here means no task failed
		return True, []

	def sign(self, workdir):
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
			print("\nSIGNING OUTPUT: " + displayname, file = self.logfile, flush = True)
			# A path with a length of 3 means we have flavour names so we append them
			displayname = displayname.split("/")
			if len(displayname) == 3:
				displayname = self.name + "-" + displayname[0] + "-" + displayname[1] + ".apk"
			else:
				displayname = self.name + "-" + displayname[0] + ".apk"
			# Verify whether is needed or not to sign, as some outputs may come out of building process already signed
			verify = subprocess.call(["apksigner", "verify", apk], stdout = self.logfile, stdin=subprocess.PIPE, stderr=subprocess.STDOUT)
			if verify == 1:
				# Sign the .apk with the provided key
				sign = subprocess.Popen(["apksigner", "sign", "--ks", self.signinfo["path"], "--ks-key-alias", self.keyalias,"--out", workdir + "/NINO-RELEASES/" + displayname, "--in", apk], stdout = self.logfile, stdin=subprocess.PIPE, stderr=subprocess.STDOUT)
				# Generate the input using the two passwords and feed it to the subprocess
				secrets = self.signinfo["password"] + "\n" + self.signinfo["aliases"][self.keyalias]["password"]
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
				os.rename(apk, workdir + "/NINO-RELEASES/" + displayname)
				print("- \033[93mUNNEEDED\033[0m")
		return releases, resign

	def install(self, workdir):
		faileddeploylist = {}
		for apk in self.deploylist:
			faileddeploylist[apk] = []
			print("DEPLOYING OUTPUT: " + apk)
			for target in self.deploylist[apk]:
				print("     TO DEVICE: " + target + " ", end = "\r")
				print("\nDEPLOYING OUTPUT " + apk + " TO DEVICE " + target, file = self.logfile, flush = True)
				try:
					# Make sure the device is online before proceeding, timeout after 15 secs of waiting
					print("     TO DEVICE: " + target + " - \033[93mCONNECTING   \033[0m", end = "\r")
					subprocess.call(["adb", "-s", target, "wait-for-device"], timeout = 15, stdout = self.logfile, stderr = subprocess.STDOUT)
				# If the adb subprocess timed out we skip this device
				except subprocess.TimeoutExpired:
					faileddeploylist[apk].append(target)
					print("     TO DEVICE: " + target + " - \033[91mNOT REACHABLE\033[0m")
					print("Not reachable", file = self.logfile, flush = True)
				else:
					print("     TO DEVICE: " + target + " - \033[93mDEPLOYING    \033[0m", end = "\r")
					# We send the apk trying to override it on the system if neccessary
					send = subprocess.call(["adb", "-s" , target, "install", "-r", workdir + "/NINO-RELEASES/" + apk], stdout = self.logfile, stderr=subprocess.STDOUT)
					if send == 0:
						print("     TO DEVICE: " + target + " - \033[92mSUCCESSFUL   \033[0m")
					else:
						faileddeploylist[apk].append(target)
						print("     TO DEVICE: " + target + " - \033[91mFAILED       \033[0m")
			if len(faileddeploylist[apk]) < 1:
				faileddeploylist.pop(apk)
		return faileddeploylist
