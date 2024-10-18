import os
import subprocess
from .statics import execprefix, fetchmethods

class fetchmethod():
	def __init__(self):
		self.type = None
		localdir = os.listdir()
		# Detect the valid fetching method for the project run
		for method in fetchmethods:
			if method in localdir:
				self.type = fetchmethods[method]
				for operation in ["lastdate", "changes", "fetch", "updated", "merge", "restore"]:
					setattr(self, operation, getattr(eval(self.type), operation))
				break
		# We need to outright store the lastdate because it will be used on project presentation
		if not self.type:
			self.lastdate = "age unknown"
			return
		self.lastdate = self.lastdate()

class custom():
	def lastdate():
		return subprocess.Popen([execprefix + "nino-sync", "lastdate"], stdout = subprocess.PIPE).communicate()[0].decode('ascii').strip()
	def changes():
		modified = subprocess.call([execprefix + "nino-sync", "changes"])
		return "Diff restore managed by custom script".encode() if modified == 0 else "".encode()
	def fetch(logfile):
		pull = subprocess.call([execprefix + "nino-sync", "fetch"], stdout = logfile, stderr = subprocess.STDOUT)
		return True if pull == 0 else False
	def updated():
		changed = subprocess.call([execprefix + "nino-sync", "updated"])
		return True if changed == 0 else False
	def merge(logfile):
		merged = subprocess.call([execprefix + "nino-sync", "merge"], stdout = logfile, stderr = subprocess.STDOUT)
		return True if merged == 0 else False
	def restore(diff, logfile):
		apply = subprocess.call([execprefix + "nino-sync", "restore"], stdout = logfile, stderr = subprocess.STDOUT)
		return True if apply == 0 else False

class git():
	def lastdate():
		return subprocess.Popen(["git", "log", "-n", "1", "--format=%cr"], stdout = subprocess.PIPE).communicate()[0].decode('ascii').strip()
	def changes():
		return subprocess.Popen(["git", "diff"], stdout = subprocess.PIPE).communicate()[0]
	def fetch(logfile):
		pull = subprocess.call(["git", "fetch"], stdout = logfile, stderr = subprocess.STDOUT)
		return True if pull == 0 else False
	def updated():
		# Branch and remote name on current local repository
		branch = subprocess.Popen(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "HEAD"], stdout = subprocess.PIPE).communicate()[0].decode('ascii').strip()
		# If we get HEAD that means we are dettached on a particular tag and we stop
		if branch == "HEAD":
			return False
		remote = subprocess.Popen(["git", "remote"], stdout = subprocess.PIPE).communicate()[0].decode('ascii').strip()
		# Amount of commits the remote is ahead of the local copy
		commitcount = subprocess.Popen(["git", "rev-list", branch + ".." + remote + "/" + branch, "--count"], stdout = subprocess.PIPE).communicate()[0].decode('ascii')
		# If the count is bigger than zero it means we can merge new stuff
		return True if int(commitcount) > 0 else False
	def merge(logfile):
		# Always clean the working dir to avoid merging issues
		subprocess.call(["git", "checkout", "."], stdout = logfile, stderr = subprocess.STDOUT)
		# Try to merge the changes
		update = subprocess.call(["git", "merge"], stdout = logfile, stderr = subprocess.STDOUT)
		return True if update == 0 else False
	def restore(diff, logfile):
		print("\n" + diff.decode() + "\n", file = logfile, flush = True)
		apply = subprocess.Popen(["git", "apply"], stdout = logfile, stderr = subprocess.STDOUT, stdin=subprocess.PIPE)
		apply.communicate(input = diff)
		return True if apply.returncode == 0 else False
