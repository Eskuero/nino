#!/usr/bin/python
import os
import git
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
		os.chdir("..")
print("The following projects have updates:" + updated)