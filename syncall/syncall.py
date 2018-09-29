#!/usr/bin/python
import os
import sys
import git
import platform
import subprocess
clean = False
command = "gradlew"
if "Windows" in platform.system():
	command += ".bat"
for arg in sys.argv:
	if arg == "--clean":
		clean = True
projects = os.listdir(".")
updated = ""
for project in projects:
	if os.path.isdir(project) and ".git" in os.listdir(project):
		os.chdir(project)
		repo = git.Repo(".").git
		lastdate = repo.log("-n", "1", "--format=%cr")
		print("------------------------------------------")
		print(project + " - last updated " + lastdate)
		print("------------------------------------------")
		result = repo.pull()
		if "Already up" not in result:
			updated += " " + project
		print(result + "\n")
		if clean and command in os.listdir("."):
			print("CLEANING GRADLE CACHE")
			subprocess.call(["./" + command, " clean"])
		os.chdir("..")
print("The following projects have updates:" + updated)