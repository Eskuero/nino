#!/usr/bin/python
import os
import sys
import git
import platform
import subprocess
clean = False
build = False
command = "gradlew"
if "Windows" in platform.system():
	command += ".bat"
for arg in sys.argv:
	if arg == "--clean":
		clean = True
	if arg == "--build":
		build = True
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
		os.chdir("..")
print("The following projects have updates:" + updated)