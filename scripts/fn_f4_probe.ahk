#Requires AutoHotkey v2.0
#SingleInstance Force
InstallKeybdHook()

logFile := A_ScriptDir "\\fn_f4_probe.log"
global ih := ""

stamp(msg) {
    global logFile
    FileAppend(FormatTime(A_Now, "yyyy-MM-dd HH:mm:ss") " | " msg "`n", logFile, "UTF-8")
    ToolTip(msg, 20, 20)
    SetTimer(() => ToolTip(), -1200)
}

toHex(n, width := 2) {
    return Format("0x{:0" width "X}", n)
}

keyNameFromVkSc(vk, sc) {
    name := GetKeyName(Format("vk{:X}sc{:X}", vk, sc))
    if (name = "") {
        name := GetKeyName(Format("vk{:X}", vk))
    }
    if (name = "") {
        name := GetKeyName(Format("sc{:X}", sc))
    }
    return name = "" ? "(unknown)" : name
}

onKeyDown(ihObj, vk, sc) {
    name := keyNameFromVkSc(vk, sc)
    stamp("DOWN name=" name " vk=" toHex(vk, 2) " sc=" toHex(sc, 3))
}

onKeyUp(ihObj, vk, sc) {
    name := keyNameFromVkSc(vk, sc)
    stamp("UP   name=" name " vk=" toHex(vk, 2) " sc=" toHex(sc, 3))
}

startLowLevelCapture() {
    global ih
    ih := InputHook("L0")
    ih.KeyOpt("{All}", "N")
    ih.VisibleText := false
    ih.VisibleNonText := false
    ih.OnKeyDown := onKeyDown
    ih.OnKeyUp := onKeyUp
    ih.Start()
}

startLowLevelCapture()
stamp("Probe started. Press Fn+F4 now. Press Ctrl+Win+K for KeyHistory. Press Esc to exit.")

^#k:: {
    KeyHistory()
    stamp("Opened KeyHistory window.")
}

~*F4:: stamp("Detected: F4")
~*vk73:: stamp("Detected: vk73 (F4 virtual key)")
~*sc03E:: stamp("Detected: sc03E (F4 scan code)")
~*Browser_Home:: stamp("Detected: Browser_Home")
~*Browser_Search:: stamp("Detected: Browser_Search")
~*Browser_Favorites:: stamp("Detected: Browser_Favorites")
~*Browser_Back:: stamp("Detected: Browser_Back")
~*Browser_Forward:: stamp("Detected: Browser_Forward")
~*Launch_Mail:: stamp("Detected: Launch_Mail")
~*Launch_App1:: stamp("Detected: Launch_App1")
~*Launch_App2:: stamp("Detected: Launch_App2")
~*Volume_Mute:: stamp("Detected: Volume_Mute")
~*Volume_Up:: stamp("Detected: Volume_Up")
~*Volume_Down:: stamp("Detected: Volume_Down")
~*Media_Play_Pause:: stamp("Detected: Media_Play_Pause")
~*Media_Next:: stamp("Detected: Media_Next")
~*Media_Prev:: stamp("Detected: Media_Prev")

Esc:: {
    stamp("Probe stopped by Esc")
    ExitApp
}
