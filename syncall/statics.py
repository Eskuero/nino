class statics():
    fetchmethods = {
        "fetch-syncall": {
            "lastdate": ["./fetch-syncall", "lastdate"],
            "diff": ["./fetch-syncall", "diff"],
            "clean": ["./fetch-syncall", "clean"],
            "pull": ["./fetch-syncall", "pull"],
            "update": ["./fetch-syncall", "update"],
            "nonews": "Already up-date",
            "apply": ["./fetch-syncall", "apply"]
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
