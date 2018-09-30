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
clean = False
build = False
command = "gradlew"
if "Windows" in platform.system():
	command += ".bat"
for i, arg in enumerate(sys.argv):
	if arg == "--clean":
		clean = True
	if arg == "--build":
		build = True
		try:
			keystore = sys.argv[i+1]
		except IndexError:
			print("You must provide a keystore file as the --build argument value for signing the release apks")
			sys.exit(1)
		else:
			if not os.path.isfile(keystore):
				print("The specified keystore file doesn't exists. Make sure you provided the correct path")
				sys.exit(1)
			else:
				password = getpass.getpass('Provide the keystore password: ')
if not os.path.isdir("SYNCALL-RELEASES"):
	os.mkdir("SYNCALL-RELEASES")
projects = os.listdir(".")
updated = ""
for project in projects:
	if os.path.isdir(project) and ".git" in os.listdir(project):
		changed = False
		os.chdir(project)
		repo = git.Repo(".").git
		lastdate = repo.log("-n", "1", "--format=%cr")
		print("------------------------------------------")
		print(project + " - last updated " + lastdate)
		print("------------------------------------------")
		result = repo.pull()
		if "Already up" not in result:
			updated += " " + project
			changed = True
		print(result + "\n")
		if command in os.listdir("."):
			if clean:
				print("CLEANING GRADLE CACHE")
				subprocess.call(["./" + command, "clean"])
			if build and changed:
				print("BUILDING GRADLE APP")
				subprocess.call(["./" + command, "assembleRelease"])
				apks = glob.glob("**/*.apk", recursive = True)
				regex = re.compile(".*build/outputs/apk/*")
				apks = list(filter(regex.match, apks))
				for apk in apks:
					subprocess.call(["zipalign", "-f", "4", apk, "aligned.apk"])
					apk = re.sub(regex, "", apk)
					apk = apk.split("/")
					name = project
					if len(apk) == 3:
						name += "-" + apk[0]
					name += ".apk"
					p = subprocess.Popen(["apksigner", "sign", "--ks", keystore, "--out", "../SYNCALL-RELEASES/" + name, "aligned.apk"], stdin=subprocess.PIPE)
					p.communicate(input=password.encode())
		os.chdir("..")
print("The following projects have updates:" + updated)