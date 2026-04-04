cmake_minimum_required(VERSION 3.20)
project(BossForgeSoundShowdown LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(BossForgeSoundDemo
    src/app/main.cpp
    src/core/Equalizer.cpp
    src/core/Upmix72.cpp
    src/core/DeviceManager.cpp
    src/core/PipelineEngine.cpp
)

target_include_directories(BossForgeSoundDemo PRIVATE src/core)
