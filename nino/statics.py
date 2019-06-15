import os
import platform

class statics():
	projects = [name for name in os.listdir() if os.path.isdir(name) and name != "NINO-RELEASES"]
	workdir = os.getcwd()
	execprefix = "" if "Windows" in platform.system() else "./"
	execsuffix = ".bat" if "Windows" in platform.system() else ""
	fetchmethods = {
		"nino-sync": {
			"lastdate": [execprefix + "nino-sync", "lastdate"],
			"diff": [execprefix + "nino-sync", "diff"],
			"clean": [execprefix + "nino-sync", "clean"],
			"pull": [execprefix + "nino-sync", "pull"],
			"update": [execprefix + "nino-sync", "update"],
			"nonews": "Already up-date",
			"apply": [execprefix + "nino-sync", "apply", "--reject"]
		},
		".git": {
			"lastdate": ["git", "log", "-n", "1", "--format=%cr"],
			"diff": ["git", "diff"],
			"clean": ["git", "checkout", "."],
			"pull": ["git", "pull"],
			"update": "",
			"nonews": "Already up",
			"apply": ["git", "apply"]
		},
		".hg": {
			"lastdate": ["hg", "log", "-l", "1", "-T", "{date|age}"], 
			"diff": ["hg", "diff"],
			"clean": ["hg", "revert", "--all"],
			"pull": ["hg", "pull"],
			"update": ["hg", "update"],
			"nonews": "no changes found",
			"apply": ["hg", "import", "--no-commit", "-"]
		}
	}
	dependencies = {
		"keytool": "https://java.com/en/download/manual.jsp",
		"git": "https://git-scm.com/book/en/v2/Getting-Started-Installing-Git",
		"hg": "https://www.mercurial-scm.org/",
		"gradle": "https://gradle.org/install/",
		"zipalign": "https://developer.android.com/studio/#downloads (build-tools)",
		"apksigner": "https://developer.android.com/studio/#downloads (build-tools)",
		"adb": "https://developer.android.com/studio/#downloads (platform-tools)"
	}
	defconfig = {
		"sync": False,
		"preserve": False,
		"build": False,
		"tasks": {
			"release": {
				"exec": "assembleRelease"
			}
		},
		"keystore": False,
		"keyalias": False,
		"deploy": []
	}
