import sys
import shutil
import argparse
import toml
from .statics import statics

class utils():
	def dpnds():
		ready = True
		for dep in statics.dependencies:
			if not shutil.which(dep):
				ready = False
				print("The required dependency '" + dep + "' is not in your PATH. Please refer to " + statics.dependencies[dep])
		if not ready:
			sys.exit(1)

	def cfgfile(rconfig):
		config = {}
		# Retrieve entire configuration from local configuration file
		try:
			with open("nino.toml", "r") as file:
				content = file.read()
				config = toml.loads(content)
		# No config file is fine
		except FileNotFoundError:
			pass
		# Update running config with avalaible values from valid definitions on config file
		defconfig = config.get("default", {})
		for option in [option for option in defconfig if option in rconfig]:
			rconfig[option] = defconfig[option]
		return config

	def cmdargs(args, rconfig, keystores):
		# Register each argument. Expect on/off for booleans, merge forced projects and deployment targets into lists and separately handle signinfo. Add an entry for retry just so is part of the help
		parser = argparse.ArgumentParser()
		parser.add_argument('-s', '--sync', choices=["on", "off"], help="Retrieve and apply changes on remote to local")
		parser.add_argument('-p', '--preserve', choices=["on", "off"], help="Try to preserve local changes after syncing remotes")
		parser.add_argument('-b', '--build', choices=["on", "off"], help="Enable building of projects")
		parser.add_argument('-f', '--force', action="append", help="Force build of a project even without changes")
		parser.add_argument('-k', '--keyinfo', help="Keystore path and alias used for signing outputs")
		parser.add_argument('-d', '--deploy', action='append', help="ADB id of a device to deploy the outputs to")
		parser.add_argument('-r', '--retry', action='store_true', help="Retry all the tasks that failed during last run")
		parser.add_argument('--version', action='version', version='%(prog)s 1.1')
		args = vars(parser.parse_args())
		# We skip any argument that comes as None because that means it was not passed
		for opt in [arg for arg in args if args[arg]]:
			if opt in ["sync", "preserve", "build"]:
				rconfig[opt] = True if args[opt] == "on" else False
			# For signing information we expect a pathfile,aliasname format
			elif opt == "keyinfo":
				try:
					storepath, rconfig["keyalias"] = args["keyinfo"].split(",")
				except:
					# Any error when retrieving the info means the format was not exactly what we expected
					parser.error('Key info must provided with the format "keypath,alias"')
				else:
					# If everything was fine setup overridestore and enable it
					keystores["overridestore"] = {"path": storepath, "aliases": {rconfig["keyalias"]: {}}}
					rconfig["keystore"] = "overridestore"
			# For everything else we store as it is
			else:
				rconfig[opt] = args[opt]
