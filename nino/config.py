import sys
import os
import json
import copy
import getpass
import subprocess
import argparse
import toml
from .statics import statics

running = {"projects": {"default": {}}, "keystores": {}, "devices": {}, "retry": False, "force": []}

# Register each argument that will be read from command line
parser = argparse.ArgumentParser()
parser.add_argument('-f', '--force', action="append", help="Force build of a project even without changes")
parser.add_argument('-r', '--retry', action='store_true', help="Retry failed tasks from previous run")
parser.add_argument('--version', action='version', version='%(prog)s 1.1')
args = vars(parser.parse_args())
# We skip any argument that comes as None because that means it was not passed
for opt in [arg for arg in args if args[arg]]:
	running[opt] = args[opt]

# The expected configuration file name varies from .nino-last (for retry mode) to nino.toml (normal mode)
filename = ".nino-last" if running["retry"] else "nino.toml"
# Retrieve entire configuration from local configuration file
try:
	with open(filename, "r") as file:
		content = json.load(file) if running["retry"] else toml.loads(file.read())
		running.update(content)
# No config file means we take all the defaults from defconfig. Spoiler: Nino does nothing
except:
	print("Failed to load config from file " + filename + ". Halting")
	sys.exit(1)

# Add missing fields in default project config using values from defconfig
for entry in statics.defconfig:
	if entry not in running["projects"]["default"]:
		running["projects"]["default"][entry] = statics.defconfig[entry]

# Retryable config that will be dumped onto .nino-last at the end, must retain keystore (before enables and promps) and device list
failed = {
	"projects": {
		"default": copy.deepcopy(running["projects"]["default"])
		},
	"keystores": copy.deepcopy(running["keystores"]),
	"devices": copy.deepcopy(running["devices"])
}

defconfig = running["projects"]["default"]
wentwrong = False
for project in statics.projects:
	# Tasks and project are referenced a couple of times so store them temporarily
	pconfig = running["projects"].get(project, {})
	tasks = pconfig.get("tasks", defconfig["tasks"])
	for task in tasks:
		# If task has build enabled we go on, else fallback to project config, and then again to defconfig
		if tasks[task].get("build", pconfig.get("build", defconfig["build"])):
			# Get the reference names for store and alias from project config
			store = tasks[task].get("keystore", pconfig.get("keystore", defconfig["keystore"]))
			alias = tasks[task].get("keyalias", pconfig.get("keyalias", defconfig["keyalias"]))
			if not store or not alias:
				print(project + ": " + task + ": build enabled but keystore/keyalias are undefined. Please review your configuration file.")
				wentwrong = True
				continue
			try:
				# Confirm that both store and alias have entries on configuration file
				running["keystores"][store]["used"] = True
				running["keystores"][store]["aliases"][alias]["used"] = True
			except KeyError:
				print(project + ": " + store + "/" + alias + " is not a valid keystore/keyalias combination. Please review your configuration file.")
				wentwrong = True
				continue
			else:
				path = running["keystores"][store].get("path", ".")
				# Make sure the absolute filesystem path exists
				if os.path.isfile(path):
					running["keystores"][store]["path"] = os.path.abspath(path)
				else:
					print(project + ": " + task + ": Path " + os.path.abspath(path) + " for keystore " + store + " does not exist. Please review your configuration file.")
					wentwrong = True
# We do not forcefully end nino until all related errors were printed
if wentwrong:
	sys.exit(1)

# Only loop through enabled keystores, as we are guaranteed to have at least one enabled keyalias
for store in [store for store in keystores if keystores[store].get("used", False)]:
	try:
		# If password was already read from config file we skip prompt
		keystores[store]["password"]
	except KeyError:
		keystores[store]["password"] = getpass.getpass("Enter password of keystore '" + store + "' (" + keystores[store]["path"] + "): ")
	# Only loop through enabled aliases
	for alias in [alias for alias in keystores[store]["aliases"] if keystores[store]["aliases"][alias].get("used", False)]:
		# Test provided password by listing keystore to see if the alias actually exists
		listing = subprocess.Popen(["keytool", "-list", "-keystore", keystores[store]["path"], "-alias", keystores[store]["aliases"][alias]["name"]], stdout = subprocess.DEVNULL, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
		listing.communicate(input=keystores[store]["password"].encode())
		if listing.returncode != 0:
			print("Keystore password is incorrect or alias '" + alias + "' (" + keystores[store]["aliases"][alias]["name"] + ") does not exist on keystore '" + store +"' (" + keystores[store]["path"] + ")")
			sys.exit(1)
		else:
			# Ask for the key password
			try:
				# If password was already read from config file we skip prompt
				keystores[store]["aliases"][alias]["password"]
			except KeyError:
				keystores[store]["aliases"][alias]["password"] = getpass.getpass("	 Enter password for key '" + alias + "' (" + keystores[store]["aliases"][alias]["name"] + ") of keystore '"+ store + "' (" + keystores[store]["path"] + "): ")
			# Attempt to export to a temporal keystore to test the alias password
			testkey = subprocess.Popen(["keytool", "-importkeystore", "-srckeystore", keystores[store]["path"], "-destkeystore", "tmpstore", "-deststorepass", "tmpstore", "-srcalias", keystores[store]["aliases"][alias]["name"]],  stdout = subprocess.DEVNULL, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
			# Generate the input using the two passwords and feed it to the subprocess
			secrets = keystores[store]["password"] + "\n" + keystores[store]["aliases"][alias]["password"]
			testkey.communicate(input=secrets.encode())
			if testkey.returncode == 0:
				# Everything was fine, delete the temporal keystore
				os.remove("tmpstore")
			else:
				print("Provided password for key '" + alias + "' (" + keystores[store]["aliases"][alias]["name"] + ") of keystore '" + store +"' (" + keystores[store]["path"] + ") is incorrect")
				sys.exit(1)
