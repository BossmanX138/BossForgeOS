#Requires AutoHotkey v2.0
#SingleInstance Force
Persistent

logFile := A_ScriptDir "\\fn_f4_messenger_guard.log"

stamp(msg) {
    global logFile
    FileAppend(FormatTime(A_Now, "yyyy-MM-dd HH:mm:ss") " | " msg "`n", logFile, "UTF-8")
    ToolTip(msg, 20, 20)
    SetTimer(() => ToolTip(), -1000)
}

closeMessengerWindows() {
    closed := 0
    winList := WinGetList("ahk_exe Messenger.exe")
    for hwnd in winList {
        try {
            WinClose("ahk_id " hwnd)
            closed += 1
        }
    }

    titleList := WinGetList("Messenger")
    for hwnd in titleList {
        try {
            WinClose("ahk_id " hwnd)
            closed += 1
        }
    }

    return closed
}

closeMessengerProcess() {
    closed := 0
    for procName in ["Messenger.exe", "MessengerApp.exe"] {
        try {
            pidList := ProcessExist(procName)
            if (pidList) {
                ProcessClose(procName)
                closed += 1
            }
        }
    }
    return closed
}

checkAndBlock() {
    w := closeMessengerWindows()
    p := closeMessengerProcess()
    if (w + p > 0) {
        stamp("Blocked Messenger launch (windows=" w ", process=" p ")")
    }
}

SetTimer(checkAndBlock, 150)
stamp("Messenger guard active. Press Esc to stop.")

Esc:: {
    stamp("Messenger guard stopped")
    ExitApp
}
