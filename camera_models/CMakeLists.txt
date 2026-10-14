cmake_minimum_required(VERSION 3.5)
project(camera_models)


set(CMAKE_CXX_STANDARD 14)
add_compile_options(-Wextra -Wpedantic)


# find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)

# # find_package(Boost REQUIRED COMPONENTS filesystem program_options system)
# # 完全禁用默认的Boost查找
# cmake_policy(SET CMP0167 NEW)

# # 手动设置Boost路径和版本
# set(Boost_USE_STATIC_LIBS OFF)
# set(Boost_USE_MULTITHREADED ON)
# set(Boost_USE_STATIC_RUNTIME OFF)

# # 设置Boost 1.83的路径
# set(BOOST_ROOT /usr)
# set(Boost_INCLUDE_DIR /usr/include)
# set(Boost_LIBRARY_DIR /usr/lib/x86_64-linux-gnu)

# # 手动设置Boost版本
# set(Boost_VERSION 1.83.0)
# set(Boost_FOUND TRUE)

# # 手动指定库文件
# set(Boost_LIBRARIES 
#     ${Boost_LIBRARY_DIR}/libboost_system.so.1.83.0
#     ${Boost_LIBRARY_DIR}/libboost_filesystem.so.1.83.0
#     ${Boost_LIBRARY_DIR}/libboost_thread.so.1.83.0
# )

# Boost配置 - 使用实际存在的1.90库
set(Boost_USE_STATIC_LIBS OFF)
set(Boost_USE_MULTITHREADED ON)
set(Boost_USE_STATIC_RUNTIME OFF)

# 直接设置Boost路径
set(Boost_INCLUDE_DIR /usr/include)
set(Boost_LIBRARY_DIR /usr/lib/x86_64-linux-gnu)

# 使用1.90的库文件（不需要system）
set(Boost_LIBRARIES 
    ${Boost_LIBRARY_DIR}/libboost_filesystem.so.1.90.0
    ${Boost_LIBRARY_DIR}/libboost_thread.so.1.90.0
    ${Boost_LIBRARY_DIR}/libboost_program_options.so.1.90.0
)

# 添加包含目录
#include_directories(${Boost_INCLUDE_DIR})
include_directories(${Boost_INCLUDE_DIRS})

find_package(OpenCV REQUIRED)
find_package(Ceres REQUIRED)
include_directories(${CERES_INCLUDE_DIRS})


ament_export_include_directories(include)
ament_export_libraries(camera_models)
ament_export_dependencies(std_msgs)

# include_directories(
#     ${catkin_INCLUDE_DIRS}
#     )

include_directories("include")

add_executable(Calibrations 
    src/intrinsic_calib.cc
    src/chessboard/Chessboard.cc
    src/calib/CameraCalibration.cc
    src/camera_models/Camera.cc
    src/camera_models/CameraFactory.cc
    src/camera_models/CostFunctionFactory.cc
    src/camera_models/PinholeCamera.cc
    src/camera_models/PinholeFullCamera.cc
    src/camera_models/CataCamera.cc
    src/camera_models/EquidistantCamera.cc
    src/camera_models/ScaramuzzaCamera.cc
    src/sparse_graph/Transform.cc
    src/gpl/gpl.cc
    src/gpl/EigenQuaternionParameterization.cc)


# added from DEBUG
# ament_target_dependencies(Calibrations rclcpp std_msgs OpenCV)
target_link_libraries(Calibrations
  rclcpp::rclcpp
  std_msgs::std_msgs
  ${OpenCV_LIBS}  # 或者 opencv_core
)

add_library(camera_models
    src/chessboard/Chessboard.cc
    src/calib/CameraCalibration.cc
    src/camera_models/Camera.cc
    src/camera_models/CameraFactory.cc
    src/camera_models/CostFunctionFactory.cc
    src/camera_models/PinholeCamera.cc
    src/camera_models/PinholeFullCamera.cc
    src/camera_models/CataCamera.cc
    src/camera_models/EquidistantCamera.cc
    src/camera_models/ScaramuzzaCamera.cc
    src/sparse_graph/Transform.cc
    src/gpl/gpl.cc
    src/gpl/EigenQuaternionParameterization.cc)

target_link_libraries(Calibrations ${Boost_LIBRARIES} ${OpenCV_LIBS} ${CERES_LIBRARIES})
target_link_libraries(camera_models ${Boost_LIBRARIES} ${OpenCV_LIBS} ${CERES_LIBRARIES})


# Install
install(TARGETS
    Calibrations
    DESTINATION lib/${PROJECT_NAME}
    )


install(TARGETS Calibrations camera_models
    ARCHIVE DESTINATION lib
    LIBRARY DESTINATION lib
    RUNTIME DESTINATION bin
)

install(TARGETS Calibrations
    RUNTIME DESTINATION lib/${PROJECT_NAME}
)
  
install(DIRECTORY include/
    DESTINATION include/
)
  


ament_package()
