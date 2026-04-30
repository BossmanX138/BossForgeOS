#Requires AutoHotkey v2.0
#SingleInstance Force
Persistent

; ===== Customize these =====
actionMode := "send"         ; send | run | text
sendKeys := "^!m"            ; used when actionMode = send
runTarget := "notepad.exe"   ; used when actionMode = run
runArgs := ""                 ; optional args for runTarget
insertText := "Fn+F4 triggered" ; used when actionMode = text
; ===========================

logFile := A_ScriptDir "\\fn_f4_repurpose.log"
lastTriggerTick := 0
cooldownMs := 900

stamp(msg) {
    global logFile
    FileAppend(FormatTime(A_Now, "yyyy-MM-dd HH:mm:ss") " | " msg "`n", logFile, "UTF-8")
    ToolTip(msg, 20, 20)
    SetTimer(() => ToolTip(), -1200)
}

closeMessenger() {
    closed := 0

    for hwnd in WinGetList("ahk_exe Messenger.exe") {
        try {
            WinClose("ahk_id " hwnd)
            closed += 1
        }
    }

    for hwnd in WinGetList("ahk_exe MessengerApp.exe") {
        try {
            WinClose("ahk_id " hwnd)
            closed += 1
        }
    }

    for procName in ["Messenger.exe", "MessengerApp.exe"] {
        try {
            if ProcessExist(procName) {
                ProcessClose(procName)
                closed += 1
            }
        }
    }

    return closed
}

runCustomAction() {
    global actionMode, sendKeys, runTarget, runArgs, insertText

    switch actionMode {
        case "send":
            Send(sendKeys)
            stamp("Action: sent keys -> " sendKeys)
        case "run":
            Run(runTarget (runArgs != "" ? " " runArgs : ""))
            stamp("Action: ran -> " runTarget)
        case "text":
            SendText(insertText)
            stamp("Action: sent text")
        default:
            stamp("Action mode invalid: " actionMode)
    }
}

fnF4ProxyTick() {
    global lastTriggerTick, cooldownMs

    blocked := closeMessenger()
    if (blocked > 0) {
        now := A_TickCount
        if (now - lastTriggerTick > cooldownMs) {
            lastTriggerTick := now
            stamp("Fn+F4 proxy detected (Messenger blocked)")
            runCustomAction()
        }
    }
}

SetTimer(fnF4ProxyTick, 120)
stamp("Fn+F4 repurpose active. Press Esc to stop. Ctrl+Win+R to reload.")

^#r:: {
    stamp("Reloading script")
    Reload
}

Esc:: {
    stamp("Script stopped")
    ExitApp
}
