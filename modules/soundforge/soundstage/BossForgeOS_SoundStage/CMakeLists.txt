cmake_minimum_required(VERSION 3.20)
project(BossForgeSoundShowdown LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(BossForgeSoundShowdown
    src/main.cpp
    src/intercept/PreSpeakerInterceptor.cpp
    src/dsp/TenBandEqualizer.cpp
    src/routing/SpeakerSelector.cpp
    src/upmix/StereoTo72Upmixer.cpp
    src/system/SystemSoundReplacementManager.cpp
    src/safety/RollbackSafetyManager.cpp
    src/ui/ConsoleControlPanel.cpp
    stubs/apo-driver/BossForgeApoStub.cpp
)

target_include_directories(BossForgeSoundShowdown PRIVATE src stubs/apo-driver)
