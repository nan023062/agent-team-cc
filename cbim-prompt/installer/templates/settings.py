SETTINGS: dict = {
    "hooks": {
        "Stop": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": "python .cbim-prompt/installer/hooks/write_memory.py",
                    }
                ]
            }
        ],
        "SessionStart": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": "python .cbim-prompt/installer/hooks/load_memory.py",
                    }
                ]
            }
        ],
    },
    "permissions": {
        "defaultMode": "bypassPermissions",
        "deny": [
            "Write(.cbim-prompt/**)",
            "Edit(.cbim-prompt/**)",
            "Glob(.cbim-prompt/**)",
            "Grep(.cbim-prompt/**)",
        ],
    },
}
