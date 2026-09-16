#Requires AutoHotkey v2.0
#SingleInstance Force
Persistent

useScanCodeMode := false
scanCodeHotkey := "sc03E"
useProxyMode := true
cooldownMs := 800
startSound := "N:\Starship_alienware\Starship Alienware(1)\hailingfrequency.wav"
stopSound := "N:\Starship_alienware\Starship Alienware(1)\messagetransmitted.wav"

lastProxyTick := 0
dictationOn := false

playSafe(path) {
    try SoundPlay(path)
    catch {
        try {
            psCmd := "
            (
            powershell -c "(New-Object Media.SoundPlayer '" path "').PlaySync()"
            )"
            Run(psCmd, , "Hide")
        } catch {
            ToolTip("Failed to play sound: " path, 20, 20)
        }
    }
}

toggleDictation(start) {
    global dictationOn, startSound, stopSound
    if start {
        playSafe(startSound)
        Send("#{h}")
        dictationOn := true
    } else {
        Send("#{h}")
        playSafe(stopSound)
        dictationOn := false
    }
}

pttHandler(*) {
    global scanCodeHotkey, startSound, stopSound
    playSafe(startSound)
    Send("#{h}")
    KeyWait(scanCodeHotkey)
    Send("#{h}")
    playSafe(stopSound)
}

closeCalculatorAndDetectLaunch() {
    launchDetected := false

    for hwnd in WinGetList("ahk_exe Calculator.exe") {
        launchDetected := true
        try WinClose("ahk_id " hwnd)
    }

    for hwnd in WinGetList("ahk_exe ApplicationFrameHost.exe") {
        title := WinGetTitle("ahk_id " hwnd)
        if InStr(title, "Calculator") {
            launchDetected := true
            try WinClose("ahk_id " hwnd)
        }
    }

    for procName in ["Calculator.exe", "calc.exe", "ApplicationFrameHost.exe"] {
        try {
            if ProcessWait(procName, 0) {
                launchDetected := true
                ProcessClose(procName)
            }
        }
    }

    return launchDetected
}

proxyTick(*) {
    global lastProxyTick, cooldownMs, dictationOn
    if closeCalculatorAndDetectLaunch() {
        now := A_TickCount
        if (now - lastProxyTick > cooldownMs) {
            lastProxyTick := now
            toggleDictation(!dictationOn)
        }
    }
}

if useScanCodeMode
    Hotkey(scanCodeHotkey, pttHandler)

if useProxyMode
    SetTimer(proxyTick, 120)

Esc::ExitApp
