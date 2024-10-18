import os
import platform

projects = [name for name in os.listdir() if os.path.isdir(name) and name != "NINO-RELEASES"]
workdir = os.getcwd()
execprefix = "" if "Windows" in platform.system() else "./"
execsuffix = ".bat" if "Windows" in platform.system() else ""
ansiescape = {
    "correct": "" if "Windows" in platform.system() else "\u001b[92m",
    "warning": "" if "Windows" in platform.system() else "\u001b[93m",
    "error": "" if "Windows" in platform.system() else "\u001b[91m",
    "close": "" if "Windows" in platform.system() else "\u001b[0m"
}
fetchmethods = {
	"nino-sync": "custom",
	".git": "git"
}
dependencies = {
	"keytool": "https://java.com/en/download/manual.jsp",
	"git": "https://git-scm.com/book/en/v2/Getting-Started-Installing-Git",
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
	"deploy": [],
	"subdir": ""
	}
