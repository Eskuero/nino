import sys
import os
import subprocess
import getpass

class signing():
	def setup(projects, config):
		keystores = {}
		# We will only save keystores used for projects existant on working directory that have build/resign enabled
		buildableprojects = [name for name in config if (name in projects or name == "default") and config[name].get("build", config["default"]["build"]) or config[name].get("resign", False)]
		for name in buildableprojects:
			path = config[name].get("keystore", config["default"]["keystore"])
			alias = config[name].get("keyalias", config["default"]["keyalias"])
			# If projects has defined keystore path and alias name we check if they exist
			if path and alias:
				if not os.path.isfile(path):
					print("The specified keystore for " + name + " does not exist: '" + path + "'")
					sys.exit(1)
				else:
					# If everything is fine we retrieve the absolute path and update the project entry with that
					path = os.path.abspath(path)
					config[name]["keystore"] = path
					# We first try to add new aliases (maybe keystore is shared by multiple projects that use different aliases)
					try:
						keystores[path]["aliases"].update({alias:None})
					# If we get KeyErrors that means keystore doesn't exist on the dict, so we initialize it
					except KeyError:
						keystores[path] = {"password": None, "aliases": {alias:None}}
			else:
				print(name + " build is enabled but lacks an assigned keystore and/or key.")
				sys.exit(1)
		return keystores

	def secrets(keystores):
		# Confirm we got an existant keystore and force
		for store in keystores:
			# Get keystore password
			keystores[store]["password"] = getpass.getpass("Enter password of keystore '" + store + "': ")
			# Try to retrieve aliases from the keystore to test password
			aliases = keystores[store].get("aliases", {})
			for alias in aliases:
				listing = subprocess.Popen(["keytool", "-list", "-keystore", store, "-alias", alias], stdout = subprocess.DEVNULL, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
				listing.communicate(input=keystores[store]["password"].encode())
				if listing.returncode != 0:
					print("Keystore password is incorrect or alias '" + alias + "' does not exist on keystore '" + store +"'")
					sys.exit(1)
				else:
					# Ask for the key password
					keystores[store]["aliases"][alias] = getpass.getpass("     Enter password for key '" + alias + "' of keystore '"+ store + "': ")
					# Attempt to export to a temporal keystore to test the alias password
					testkey = subprocess.Popen(["keytool", "-importkeystore", "-srckeystore", store, "-destkeystore", "tmpstore", "-deststorepass", "tmpstore", "-srcalias", alias],  stdout = subprocess.DEVNULL, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
					# Generate the input using the two passwords and feed it to the subprocess
					secrets = keystores[store]["password"] + "\n" + keystores[store]["aliases"][alias]
					testkey.communicate(input=secrets.encode())
					if testkey.returncode == 0:
						# Everything was fine, delete the temporal keystore
						os.remove("tmpstore")
					else:
						print("Provided password for key '" + alias + "' of keystore '" + store +"' is incorrect")
						sys.exit(1)
