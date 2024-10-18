import os
import pathlib
import re
import subprocess
import copy
from .config import running
from .utils import cprint
from .fetchmethods import fetchmethod
from .statics import execprefix, execsuffix, workdir, defconfig

class project():
	def __init__(self, name):
		self.name = name
		pconfig = running["projects"].get(name, {})
		# Retrieve value for each property except for force because has different types
		for prop in defconfig:
			setattr(self, prop, pconfig.get(prop, running["projects"]["default"][prop]))
		# Detect the valid fetching method even when fetching is disabled because is needed on presentation
		self.fetcher = fetchmethod()
		# Remember subdir in case we need it for retries
		self.subdir = pconfig.get("subdir", False)
		# Forcing stores a list from cmdargs and a bool on project so check both
		self.force = name in running["force"] or pconfig.get("force", False)
		# Some properties are only generated by nino in the scope of retrying so avoid user interference
		self.signlist = pconfig.get("signlist", {}) if running["retry"] else {}
		self.deploylist = pconfig.get("deploylist", {}) if running["retry"] else {}
		# Some properties are exclusive for the run
		self.changed, self.built, self.failed, self.releases = False, 1, {}, set()

	def presentation(self):
		# Retrieve and show basic information about the project
		print("------------------------------------------")
		print(self.name + " - last updated " + self.fetcher.lastdate)

	def fetch(self):
		# Without any valid fetching methods we skip syncing
		if not self.fetcher.type:
			cprint("No valid fetching method available", "warning")
			return
		print("SYNCING SOURCE CODE (" + self.fetcher.type + "):")
		print("     FETCHING REMOTE - ", end = "", flush = True)
		# Pull changes from remote and proceed if it went fine
		if self.fetcher.fetch(self.logfile):
			# Check if there are new changes available before proceeding, else we stop here
			checker = self.fetcher.newtag() if self.followtags else self.fetcher.updated()
			if checker[0]:
				cprint("UPDATED", "correct")
				# Now we must merge changes into working tree
				print("     MERGING REMOTE - ", end = "", flush = True)
				# Store the current local diff to restore it later if enabled
				if self.preserve:
					diff = self.fetcher.changes()
				merger = self.fetcher.tagswap(self.logfile, checker[1]) if self.followtags else self.fetcher.merge(self.logfile)
				if merger:
					self.changed = True
					cprint("SUCCESSFUL", "correct")
				else:
					# Merging went bad
					self.failed.update({"sync": self.sync, "followtags": self.followtags, "preserve": self.preserve, "subdir": self.subdir, "build": self.build, "force": self.force, "tasks": self.tasks, "keystore": self.keystore, "keyalias": self.keyalias, "signlist": self.signlist, "deploylist": self.deploylist, "deploy": self.deploy})
					cprint("FAILED", "error")
				# Now try to restore the local changes if they actually exist
				if self.preserve and diff.decode() != "":
					print("     RESTORING LOCAL CHANGES - ", end = "", flush = True)
					if self.fetcher.restore(diff, self.logfile):
						cprint("SUCCESSFUL", "correct")
					else:
						# Failure on restore means we skip building for this run to allow the user to fix the conflict once
						self.failed.update({"sync": not self.changed, "followtags": self.followtags, "preserve": self.preserve, "subdir": self.subdir, "build": self.build, "force": self.changed, "tasks": self.tasks, "keystore": self.keystore, "keyalias": self.keyalias, "signlist": self.signlist, "deploylist": self.deploylist, "deploy": self.deploy})
						self.build = False
						cprint("FAILED", "error")
			else:
				cprint("UNCHANGED", "warning")
				return
		else:
			# Pulling went bad :(
			self.failed.update({"sync": self.sync, "followtags": self.followtags, "preserve": self.preserve, "subdir": self.subdir, "build": self.build, "force": self.force, "tasks": self.tasks, "keystore": self.keystore, "keyalias": self.keyalias, "signlist": self.signlist, "deploylist": self.deploylist, "deploy": self.deploy})
			cprint("FAILED", "error")

	def package(self):
		print("BUILDING PACKAGE:")
		# User may provide an entrypoint that must be used as setup script before building
		if os.path.isfile("nino-entrypoint" + execsuffix):
			print("     ENTRYPOINT SCRIPT - ", end = "", flush = True)
			# Attempt to do the setup
			self.built = subprocess.call([execprefix + "nino-entrypoint"], stdout = self.logfile, stderr = subprocess.STDOUT)
			if self.built != 0:
				cprint("FAILED", "error")
				self.failed.update({"subdir": self.subdir, "build": self.build, "force": True, "tasks": self.tasks, "keystore": self.keystore, "keyalias": self.keyalias, "signlist": self.signlist, "deploylist": self.deploylist, "deploy": self.deploy})
				return
			else:
				cprint("SUCCESSFUL", "correct")

		# If project specifies a subdir for building get in there
		if self.subdir:
			os.chdir(self.subdir)
		# Check if gradle wrapper exists before falling back to system-wide gradle
		if not os.path.isfile("gradlew" + execsuffix):
			command = "gradle"
		else:
			command = execprefix + "gradlew" + execsuffix
		for task in self.tasks:
			print("     GRADLE TASK " + task + " - ", end = "", flush = True)
			# Attempt the task, we also redirect stderr to stdout to effectively merge them.
			self.built = subprocess.call([command, "--no-daemon", self.tasks[task]["exec"]], stdout = self.logfile, stderr = subprocess.STDOUT)
			# If assembling fails we return to tell main
			if self.built != 0:
				cprint("FAILED", "error")
				# Save for retry only the failed tasks
				if "tasks" not in self.failed:
					self.failed["tasks"] = {}
				self.failed["tasks"].update({task: self.tasks[task]})
				self.failed.update({"subdir": self.subdir, "build": self.build, "force": True, "tasks": self.failed["tasks"], "keystore": self.keystore, "keyalias": self.keyalias, "signlist": self.signlist, "deploylist": self.deploylist, "deploy": self.deploy})
			else:
				self.updatesignlist(task)
				cprint("SUCCESSFUL", "correct")

	def updatesignlist(self, task):
		# Retrieve all present .apk inside projects folder
		apks = [str(apk) for apk in pathlib.Path().glob("**/*.apk")]
		# Filter out those that are not result of a Gradle task
		validroutes = re.compile(".*build(\\\\|\/).*outputs(\\\\|\/).*apk(\\\\|\/)")
		# Filter out those remaining from a previous failed task
		previous = copy.deepcopy(self.releases)
		self.releases = set(filter(validroutes.match, apks))
		# Discover which one are the outputs corresponding to the just finished task
		new = previous.symmetric_difference(self.releases)
		# Create a dictionary for each route containing apks
		outputs = {}
		apkroute = re.compile("[^\\\\|\/]*\.apk")
		for apk in new:
			# Determine the apk full route inside project
			route = re.sub(apkroute, "", apk)
			if route not in outputs:
				outputs[route] = {"apks": [], "splitnames": []}
			# Append each apk to the route index on the diccionary
			outputs[route]["apks"].append(apk)
		# Obtain the differences in the names of apks inside routes containing more than one output, because that means they must be treated as splitted apks
		for route in [route for route in outputs if len(outputs[route]["apks"]) > 1]:
			previous = outputs[route]["apks"][1].split("-")
			for apk in outputs[route]["apks"]:
				current = apk.split("-")
				# Get split names inside the list and join them back again
				differences = [item for item in current if item not in previous]
				outputs[route]["splitnames"].append("-".join(differences))
				previous = current
		# We are finally ready to prepare the signlist
		for route in outputs:
			for index, apk in enumerate(outputs[route]["apks"]):
				# Generate displayname from project name + task
				displayname = re.sub(validroutes, "", apk)
				# A path with a length of 3 means we have flavour names so we append them
				displayname = re.split("\\\\|\/", displayname)
				if len(displayname) == 3:
					displayname = self.name + "-" + task + "-" + displayname[0]
				else:
					displayname = self.name + "-" + task
				# Get keystore, keyalias and deploy targets from task if they exist, else fallback to project, which already fell back to defconfig
				keystore = self.tasks[task].get("keystore", self.keystore)
				keyalias = self.tasks[task].get("keyalias", self.keyalias)
				deploy = self.tasks[task].get("deploy", self.deploy)
				# Append split name if required (there's more than one apk in the route)
				if len(outputs[route]["apks"]) > 1:
					displayname = displayname + "-" + outputs[route]["splitnames"][index]
					# Override deploy configuration if specified
					if outputs[route]["splitnames"][index] in self.tasks[task].get("splits", []):
						deploy = self.tasks[task]["splits"][outputs[route]["splitnames"][index]].get("deploy", deploy)
				# Create a new entry with all the required data to continue the process
				self.signlist[apk] = {
					"displayname": displayname + ".apk",
					"keystore": keystore,
					"keyalias": keyalias,
					"deploy": deploy
				}


	def sign(self):
		print("SIGNING OUTPUTS:")
		# Store the list of failed to sign outpusts and devices to deploy later on a different dict
		failedsignlist = {}
		# Loop through the remaining apks (there may be different flavours)
		for apk in self.signlist:
			print("     " + self.signlist[apk]["displayname"] + " - ", end = "", flush = True)
			# Verify whether is needed or not to sign, as some outputs may come out of building process already signed
			verify = subprocess.call(["apksigner" + execsuffix, "verify", apk], stdout = self.logfile, stdin=subprocess.PIPE, stderr=subprocess.STDOUT)
			if verify == 1:
				# Sign the .apk with the provided key
				sign = subprocess.Popen(["apksigner" + execsuffix, "sign", "--ks", running["keystores"][self.signlist[apk]["keystore"]]["path"], "--ks-key-alias", running["keystores"][self.signlist[apk]["keystore"]]["aliases"][self.signlist[apk]["keyalias"]]["name"],"--out", workdir + "/NINO-RELEASES/" + self.signlist[apk]["displayname"], "--in", apk], stdout = self.logfile, stdin=subprocess.PIPE, stderr=subprocess.STDOUT)
				# Generate the input using the two passwords and feed it to the subprocess
				secrets = running["keystores"][self.signlist[apk]["keystore"]]["password"] + "\n" + running["keystores"][self.signlist[apk]["keystore"]]["aliases"][self.signlist[apk]["keyalias"]]["password"]
				sign.communicate(input=secrets.encode())
				if sign.returncode == 0:
					# If everything went fine add the new .apk to the list of releases
					self.updatedeploylist(self.signlist[apk]["displayname"], self.signlist[apk]["deploy"])
					os.remove(apk)
					cprint("SUCCESSFUL", "correct")
				else:
					failedsignlist[apk] = self.signlist[apk]
					cprint("FAILED", "error")
			else:
				self.updatedeploylist(self.signlist[apk]["displayname"], self.signlist[apk]["deploy"])
				os.rename(apk, workdir + "/NINO-RELEASES/" + self.signlist[apk]["displayname"])
				cprint("UNNEEDED", "warning")
		# If we failed at least on one output we need to save it for the retry run
		if failedsignlist:
			self.failed.update({"keystore": self.keystore, "keyalias": self.keyalias, "signlist": failedsignlist, "deploylist": self.deploylist, "deploy": self.deploy})

	def updatedeploylist(self, apk, targets):
		devices = set()
		for roster in targets:
			devices = devices.union(set(running["devices"].get(roster, [])))
		self.deploylist[apk] = list(devices)

	def install(self):
		print("DEPLOYING OUTPUTS:")
		# Store the list of failed to deploy outputs and devices on a different dict
		faileddeploylist = {}
		for apk in self.deploylist:
			print("     " + apk + " - ", end = "", flush = True)
			# If no target is specified for the output we skip this iteration
			if not self.deploylist[apk]:
				cprint("NO TARGETS", "warning")
				continue
			else:
				print()
			faileddeploylist[apk] = []
			for target in self.deploylist[apk]:
				print("          TO DEVICE " + target + " - ", end = "\r")
				try:
					# Make sure the device is online before proceeding, timeout after 15 secs of waiting
					cprint("          TO DEVICE " + target + " CONNECTING   ", "warning", "\r")
					subprocess.call(["adb", "-s", target, "wait-for-device"], timeout = 15, stdout = self.logfile, stderr = subprocess.STDOUT)
				# If the adb subprocess timed out we skip this device
				except subprocess.TimeoutExpired:
					faileddeploylist[apk].append(target)
					cprint("          TO DEVICE " + target + " NOT REACHABLE", "error")
					print("Not reachable", file = self.logfile, flush = True)
				else:
					cprint("          TO DEVICE " + target + " DEPLOYING    ", "warning", "\r")
					# We send the apk trying to override it on the system if neccessary
					send = subprocess.call(["adb", "-s" , target, "install", "-r", workdir + "/NINO-RELEASES/" + apk], stdout = self.logfile, stderr=subprocess.STDOUT)
					if send == 0:
						cprint("          TO DEVICE " + target + " SUCCESSFUL   ", "correct")
					else:
						faileddeploylist[apk].append(target)
						cprint("          TO DEVICE " + target + " FAILED       ", "error")
			if len(faileddeploylist[apk]) < 1:
				faileddeploylist.pop(apk)
		# We need to retry if at least one output wasn't delivered
		if faileddeploylist:
			self.failed.update({"deploylist": faileddeploylist, "deploy": self.deploy})
