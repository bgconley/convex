#!/usr/bin/env ruby
# frozen_string_literal: true

require 'fileutils'
require 'pathname'
require 'xcodeproj'

ROOT = Pathname.new(__dir__).join('..').expand_path
PROJECT_PATH = ROOT.join('Cortex.xcodeproj')
APP_NAME = 'Cortex'
TARGET_NAME = 'CortexMac'
BUNDLE_ID = 'com.brennanconley.cortex'

FileUtils.rm_rf(PROJECT_PATH)

project = Xcodeproj::Project.new(PROJECT_PATH.to_s)
project.root_object.attributes['LastSwiftUpdateCheck'] = '2600'
project.root_object.attributes['LastUpgradeCheck'] = '2600'

app_target = project.new_target(:application, TARGET_NAME, :osx, '14.0')
app_target.product_name = APP_NAME

project.main_group.set_source_tree('SOURCE_ROOT')
app_group = project.main_group.find_subpath('AppHost', true)
sources_group = app_group.find_subpath('Sources', true)
config_group = app_group.find_subpath('Config', true)

source_ref = sources_group.new_file('AppHost/Sources/CortexHostApp.swift')
plist_ref = config_group.new_file('AppHost/Config/Info.plist')
app_target.add_file_references([source_ref])

local_package = project.new(Xcodeproj::Project::Object::XCLocalSwiftPackageReference)
local_package.relative_path = '.'
project.root_object.package_references << local_package

package_product = project.new(Xcodeproj::Project::Object::XCSwiftPackageProductDependency)
package_product.package = local_package
package_product.product_name = 'CortexApp'
app_target.package_product_dependencies << package_product

target_dependency = project.new(Xcodeproj::Project::Object::PBXTargetDependency)
target_dependency.product_ref = package_product
app_target.dependencies << target_dependency

build_file = project.new(Xcodeproj::Project::Object::PBXBuildFile)
build_file.product_ref = package_product
app_target.frameworks_build_phase.files << build_file

app_target.build_configurations.each do |config|
    config.build_settings['PRODUCT_BUNDLE_IDENTIFIER'] = BUNDLE_ID
    config.build_settings['GENERATE_INFOPLIST_FILE'] = 'NO'
    config.build_settings['INFOPLIST_FILE'] = plist_ref.path
    config.build_settings['CODE_SIGN_STYLE'] = 'Automatic'
    config.build_settings['SWIFT_VERSION'] = '6.0'
    config.build_settings['MACOSX_DEPLOYMENT_TARGET'] = '14.0'
    config.build_settings['ENABLE_HARDENED_RUNTIME'] = 'NO'
    config.build_settings['LD_RUNPATH_SEARCH_PATHS'] = '$(inherited) @executable_path/../Frameworks @loader_path/../Frameworks'
    config.build_settings['PRODUCT_NAME'] = APP_NAME
end

project.save
puts "Generated #{PROJECT_PATH}"
