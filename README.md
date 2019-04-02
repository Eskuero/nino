
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

The script depends on the toml python library (will be automatically installed by pip) and requires having keytool (Java OpenJDK), adb (Android Debug Bridge), apksigner (Android SDK build tools), zipalign (Android SDK Build Tools), gradle (in case any of the projects do not provide a gradle wrapper) and git on the PATH of your running operative system.
Each project may also have additional dependencies to build binaries.

## Usage
By default executing the command without arguments/config file will result into it synchronizing all the git repositories in the immediate subfolders.
```
syncall.py
```

### Configuration file
The recommended configuration format is to use a syncall.toml file in the working directory, as it allows granularity with per-project settings.

- In the following example we enable **fetching remote** and **preserving local** changes.
- We also enable **building for all the projects** and signing them using the **key "mykey"** from the **keystore "default"** (clave.jks).
- All the **output files will be deployed** to the **list of devices with the given ID**, may it be an IP addresss/port combination or a serial number.
- It defines **two keystores**, one named **"default"** that contains "mykey" and "myke2" keys, and another named **"otherkey"** that only contains the "another" alias, but provides both **passwords without prompting** the user.

Per project specific we have the following settings:
- **Signal-Android** project it would always force building of the app using the assemblePlayRelease and assembleWebsiteRelease tasks, in that order.
- **Conversations** project it would attempt the assembleConversationsFreeSystemRelease task and sign it with the key "another" inside the store "otherkey" (keystore.jks)
- **vlc-android** project it would use all the default values except that it will run the script named "entrypoint-syncall" from project's folder before executing any gradle task.
- **ghost-project** project will never build
```
[default]
fetch = true
preserve = true
build = true
keystore = "default"
keyalias = "mykey"
deploy = ["DT456VP6T7", "192.168.10.40:5555"]

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

[vlc-android]
entrypoint = true

[ghost-project]
build = false
```

### Fetching
If enabled by default the script will try to fetch changes, however you can skip that passing --fetch. This is very useful for situations where you just want to rebuild local changes for a certain application without wanting to go through all the projects. Per example:
```
syncall --fetch=n --force=Shelter
```
Would force building of the Shelter project without fetching changes on any project.

### Building
If you want to not only the sync the source code but also to compile the app when new changes are detected during the current syncing interation you must use it like this:
```
syncall.py --build=/path/to/key.jks,keyalias
```
The --build argument expects to be passed alongside the absolute or relative path to a Java key store containing the key named as keyalias. You will be prompted to enter both passwords. It also accepts a value of n to disable building.
All the output files will be automatically signed with the provided key, and then placed a SYNCALL-RELEASES folder on the working dir.

### Deploying
The script can make use of adb to automatically deploy the built and signed apk on your devices. Each installation will timeout at 15 seconds if the specified device ID is not attached. You can override the configuration file defaults by providing a comma separated list of devices using the following command line argument:
```
syncall.py --deploy=DT456VP6T6,192.168.10.44:4444
```
This would attempt to deploy by default to DT456VP6T6 and 192.168.10.44:4444 unless specific project configuration says otherwise.
For more information regarding adb usage and connection see the official documentation:
<https://developer.android.com/studio/command-line/adb>

### Retrying
The script will save a list of what failed for each project of the previous interation in a .last-syncall file at the working folder. This is so you can retry building after figuring what caused the issues.
```
syncall.py --retry=y
```
Retrying is more of a mode rather than an option, any other command line arguments passed alongside will be ignored and the configuration file won't be parsed.

### Forcing
Sometimes you may want to rebuild certain apps even if no upstream changes are received (offline project, no internet connection, just testing local changes...). You can do so by passing a list of comma joined project names (their folder name) alongside the --force argument:
```
syncall.py --build=/path/to/key.jks,keyalias --force=Signal-Android,Tusky,SomeOtherProject
```

### Preserving local changes
If you wish to preserve local changes tracked but not staged for commit you can use the --preserve flag, that commands the script to generate a diff of the current changes and to attempt on restoring it later. This is very useful to hold onto minor customizations you may want to apply to the app:
```
syncall --build=/path/to/key.jks,keyalias --preserve=y
```
Would attempt to build all projects with changes preserving local changes made to them
