cmake_minimum_required(VERSION 3.8)
project(vins)

set(CMAKE_CXX_STANDARD 14)
add_compile_options(-Wextra -Wpedantic)

set(CMAKE_BUILD_TYPE Release)



# find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rcpputils REQUIRED)
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(visualization_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(tf2 REQUIRED)
find_package(tf2_ros REQUIRED)
find_package(tf2_geometry_msgs REQUIRED)
find_package(cv_bridge REQUIRED)
find_package(camera_models REQUIRED)
find_package(image_transport REQUIRED)

find_package(OpenCV REQUIRED)
find_package(Ceres REQUIRED)

# 添加包含目录
include_directories(${CERES_INCLUDE_DIRS})
include_directories("../camera_models/include")

set(CMAKE_MODULE_PATH ${PROJECT_SOURCE_DIR}/cmake)
find_package(Eigen3 REQUIRED)
include_directories(${EIGEN3_INCLUDE_DIR})

# 添加库目录（如果需要）
link_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/../camera_models/build
    /run/media/sydai/disk/git_ws/vins_ws/install/camera_models/lib
)

# 创建 vins_lib 库
add_library(vins_lib
    src/estimator/parameters.cpp
    src/estimator/estimator.cpp
    src/estimator/feature_manager.cpp
    src/factor/pose_local_parameterization.cpp
    src/factor/projectionTwoFrameOneCamFactor.cpp
    src/factor/projectionTwoFrameTwoCamFactor.cpp
    src/factor/projectionOneFrameTwoCamFactor.cpp
    src/factor/marginalization_factor.cpp
    src/utility/utility.cpp
    src/utility/visualization.cpp
    src/utility/CameraPoseVisualization.cpp
    src/initial/solve_5pts.cpp
    src/initial/initial_aligment.cpp
    src/initial/initial_sfm.cpp
    src/initial/initial_ex_rotation.cpp
    src/featureTracker/feature_tracker.cpp
)

# 链接 vins_lib 的依赖
target_link_libraries(vins_lib
    ${OpenCV_LIBS}
    ${CERES_LIBRARIES}
    rclcpp::rclcpp
    rcpputils::rcpputils
    std_msgs::std_msgs
    visualization_msgs::visualization_msgs
    geometry_msgs::geometry_msgs
    nav_msgs::nav_msgs
    tf2::tf2
    tf2_ros::tf2_ros
    tf2_geometry_msgs::tf2_geometry_msgs
    cv_bridge::cv_bridge
    camera_models
    image_transport::image_transport
)

# vins_node 可执行文件
add_executable(vins_node src/rosNodeTest.cpp)
target_link_libraries(vins_node
    vins_lib
    rclcpp::rclcpp
    rcpputils::rcpputils
    std_msgs::std_msgs
    visualization_msgs::visualization_msgs
    geometry_msgs::geometry_msgs
    nav_msgs::nav_msgs
    tf2::tf2
    tf2_ros::tf2_ros
    tf2_geometry_msgs::tf2_geometry_msgs
    cv_bridge::cv_bridge
    camera_models
    image_transport::image_transport
    ${OpenCV_LIBS}
    ${CERES_LIBRARIES}
)

# kitti_odom_test 可执行文件
add_executable(kitti_odom_test src/KITTIOdomTest.cpp)
target_link_libraries(kitti_odom_test
    vins_lib
    rclcpp::rclcpp
    rcpputils::rcpputils
    std_msgs::std_msgs
    visualization_msgs::visualization_msgs
    geometry_msgs::geometry_msgs
    nav_msgs::nav_msgs
    tf2::tf2
    tf2_ros::tf2_ros
    tf2_geometry_msgs::tf2_geometry_msgs
    cv_bridge::cv_bridge
    camera_models
    image_transport::image_transport
    ${OpenCV_LIBS}
    ${CERES_LIBRARIES}
)

# kitti_gps_test 可执行文件
add_executable(kitti_gps_test src/KITTIGPSTest.cpp)
target_link_libraries(kitti_gps_test
    vins_lib
    rclcpp::rclcpp
    rcpputils::rcpputils
    std_msgs::std_msgs
    visualization_msgs::visualization_msgs
    geometry_msgs::geometry_msgs
    nav_msgs::nav_msgs
    tf2::tf2
    tf2_ros::tf2_ros
    tf2_geometry_msgs::tf2_geometry_msgs
    cv_bridge::cv_bridge
    camera_models
    image_transport::image_transport
    ${OpenCV_LIBS}
    ${CERES_LIBRARIES}
)

# Install launch files
install(
    DIRECTORY launch/
    DESTINATION share/${PROJECT_NAME}/launch/
)

# Install config files
install(
    DIRECTORY ../config/
    DESTINATION share/${PROJECT_NAME}/config/
)

set_target_properties(vins_node PROPERTIES
    INSTALL_RPATH "$ORIGIN/.."
    BUILD_WITH_INSTALL_RPATH TRUE)

# Install nodes
install(
    TARGETS vins_node
    DESTINATION lib/${PROJECT_NAME}
)
# Install shared library
# install(
#     TARGETS vins_lib
#     LIBRARY DESTINATION lib
#     ARCHIVE DESTINATION lib
#     RUNTIME DESTINATION lib
# )

ament_package()