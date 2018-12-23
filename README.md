# Syncall: Keep your Android apps updated
Do you like to get the latest features of the apps first than anyone?
Do you want to manually build everything to confirm the source code matches the binaries distributed by the developer?

You can use this Python script to automatically sync, build and sign all of your open source apps using gradle. It will download the latest copy of the source code from the git repository provided, proceed to build if changes are detected, to later sign the outputs and finally provide a ready to install .apk file.

## Installation
Clone this git repository and install it using pip:
```
$ git clone https://github.com/Eskuero/syncall.git
$ cd syncall
# pip install .
```

The script depends on the toml python library (will be automatically installed by pip) and requires having keytool (Java OpenJDK), apksigner (Android SDK build tools), zipalign (Android SDK Build Tools) and git on the PATH of your running operative system.

## Usage
By default executing the command without arguments/config file will result into it synchronizing all the git repositories in the immediate subfolders.
```
syncall.py
```

### Configuration file
All the command line arguments specified below can be defined as defaults on a toml configuration file on the working directory named as syncall.toml.
This requires the installation of the toml parser:
```
pip install toml
```
Per example the following content would disable retrying by default while enabling building for all the projects, using the key "mykey" inside keystore "default" (clave.jks) and trying to keep local changes.
It defines two keystores, one named "default" that contains "mykey" and "myke2" keys, and another named "otherkey" that only contains the "another" alias, but provides both passwords without prompting the user.
For the Signal-Android project it would always force building of the app using the assemblePlayRelease and assembleWebsiteRelease tasks, in that order.
It will also build the Conversations project with the assembleConversationsFreeSystemRelease task and sign it with the key "another" inside the store "otherkey" (keystore.jks)
```
[default]
fetch = true
preserve = true
build = true
retry = false
keystore = "default"
keyalias = "mykey"

[keystores]
	[keystores.default]
		path = "clave.jks"
		[keystores.default.aliases]
			[keystores.default.aliases.mykey]
			[keystores.default.aliases.myke2]
	[keystores.otherkey]
		path = "keystore.jks"
		password = "password"
		[keystores.someother.aliases]
			[keystores.someother.aliases.another]
				password = "123456"

[Signal-Android]
force = true
tasks = ["assemblePlayRelease", "assembleWebsiteRelease"]

[Conversations]
keystore = "otherkey"
keyalias = "another"
tasks = ["assembleConversationsFreeSystemRelease"]
```

### Fetching
By default the script will try to fetch changes for all projects, however you can skip that passing --fetch. This is very useful for situations where you just want to rebuild local changes without wanting to go through all the projects, per example:
```
syncall --fetch=n --build=/path/to/key.jks --force=Shelter
```
Would force building of the Shelter project without fetching changes on any project.

### Building
If you want to not only the sync the source code but also to compile the app when new changes are detected during the current syncing interation you must use it like this:
```
syncall.py --build=/path/to/key.jks,keyalias
```
The --build argument expects to be passed alongside the absolute or relative path to a Java key store containing the key named as keyalias. You will be prompted to enter both passwords. It also accepts a value of n to disable building.
All the output files will be automatically aligned and signed with the provided key, and then placed a SYNCALL-RELEASES folder on the working dir.

### Retrying
The script will save a list of the failed projects in the previous interation in the .retry-projects of the working folder. It also will report to you a list of which specific task failed at the end of the run. This is so you can retry building after maybe figuring out any issues.
To do so:
```
syncall.py --build=/path/to/key.jks --retry=y
```
The --retry command does not need any value, but requires the keystore to be set with the --build command because otherwise the .apk would not be signed.

### Forcing
Sometimes you may want to rebuild certain apps even if no upstream changes are received (offline project, no internet connection, just testing local changes...). You can do so by passing a list of comma joined project names (their folder name) alongside the --force argument:
```
syncall.py --build=/path/to/key.jks --force=Signal-Android,Tusky,SomeOtherProject
```
Requires the keystore to be set with the --build command because otherwise the .apk would not be signed.

### Preserving local changes
If you wish to preserve local changes tracked but not staged for commit you can use the --preserve flag, that commands the script to generate a diff of the current changes and to attempt on restoring it later. This is very useful to hold onto minor changes like gradle version bumps to fix compilation issues without having to reapply them on every update.
Per example:
```
syncall --build=/path/to/key.jks --preserve=y
```
Would attempt to build all projects with changes preserving local changes made to them
