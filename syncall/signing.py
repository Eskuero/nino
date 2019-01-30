import sys
import os
import subprocess
import getpass

class signing():
	def enable(config, projects, keystores, rconfig):
		# Enable custom keystores defined for each project
		for name in config:
			if not name == "keystores" and (name in projects or (name == "default" and "overridestore" not in keystores and rconfig["build"])):
				# Retrieve the path only if building, either from default or custom
				if config[name].get("build", rconfig["build"]):
					store = config[name].get("keystore", rconfig["keystore"])
					alias = config[name].get("keyalias", rconfig["keyalias"])
					# Only if path is defined and in use
					if store and alias:
						if alias in keystores.get(store, {}).get("aliases", {}):
							keystores[store]["used"] = True
							keystores[store]["aliases"][alias]["used"] = True
						else:
							print("The specified keystore/key alias combination for " + name + " doesn't exist on configuration file")
							sys.exit(1)
					else:
						print(name + " build is enabled but lacks an assigned keystore and/or key.")
						sys.exit(1)
		return signing.secrets(keystores)
		
	def secrets(keystores):
		# Confirm we got an existant keystore and force
		for store in keystores:
			# If the keystore won't be used we skip it altogether
			if keystores[store].get("used", False):
				# Make sure the specified path for the keystore exists
				path = keystores[store].get("path", "")
				if not os.path.isfile(path):
					print("The specified path for " + store + " keystore does not exist: '" + path + "'")
					sys.exit(1)
				else:
					# Make sure we save the full path
					keystores[store]["path"] = os.path.abspath(keystores[store]["path"])
					# Ask for the keystore password
					try:
						keystores[store]["password"]
					except KeyError:
						keystores[store]["password"] = getpass.getpass("Enter password of '" + store + "' keystore '"+ keystores[store]["path"] + "': ")
					# Try to retrieve aliases from the keystore to test password
					aliases = keystores[store].get("aliases", {})
					for alias in (alias for alias in aliases if keystores[store]["aliases"][alias].get("used", False)):
						listing = subprocess.Popen(["keytool", "-list", "-keystore", keystores[store]["path"], "-alias", alias], stdout = subprocess.DEVNULL, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
						listing.communicate(input=keystores[store]["password"].encode())
						if listing.returncode != 0:
							print("Keystore password is incorrect or alias '" + alias + "' does not exist on keystore")
							sys.exit(1)
						else:
							# Ask for the key password
							try:
								keystores[store]["aliases"][alias]["password"]
							except KeyError:
								keystores[store]["aliases"][alias]["password"] = getpass.getpass("     Enter password for key '" + alias + "' of '" + store + "' keystore '"+ keystores[store]["path"] + "': ")
							# Attempt to export to a temporal keystore to test the alias password
							testkey = subprocess.Popen(["keytool", "-importkeystore", "-srckeystore", keystores[store]["path"], "-destkeystore", "tmpstore", "-deststorepass", "tmpstore", "-srcalias", alias],  stdout = subprocess.DEVNULL, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
							# Generate the input using the two passwords and feed it to the subprocess
							secrets = keystores[store]["password"] + "\n" + keystores[store]["aliases"][alias]["password"]
							testkey.communicate(input=secrets.encode())
							if testkey.returncode == 0:
								# Everything was fine, delete the temporal keystore
								os.remove("tmpstore")
							else:
								print("Provided password for key '" + alias + "' of keystore '" + keystores[store]["path"] +"' is incorrect")
								sys.exit(1)
		return keystores						
