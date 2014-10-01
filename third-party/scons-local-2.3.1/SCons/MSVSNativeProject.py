#
# IMVU CUSTOM VISUAL STUDIO PROJECT BUILDER
# This builder generates a Microsoft Visual Studio Project for Visual Studio 12.0\
# Unlike the normal MSVSProject generated by SCons, this project will use
# Visual Studio to build natively - not SCons.
# The project is put into the build directory the user requested -
# not in the directory containing the SCONS file.
#
# To invoke this builder set Environment variable MSVSPROJECTCOM to
#   "SCons.Action.Action(SCons.MSVSNativeProject.GenerateVCXProject"
#
# Nola Donato April 2014
#

import SCons.compat

import base64
import hashlib
import ntpath
import os
import re
import sys

import SCons.Builder
import SCons.Node.FS
import SCons.Platform.win32
import SCons.Script.SConscript
import SCons.PathList
import SCons.Util
import SCons.Warnings
from SCons.Tool.msvs import msvs_parse_version, Config, _DSPGenerator as _ProjGenerator


def xmlify(s):
    s = s.replace("&", "&amp;") # do this first
    s = s.replace("'", "&apos;")
    s = s.replace('"', "&quot;")
    return s

# Process a CPPPATH list in includes, given the env, target and source.
# Returns a tuple of nodes.
def processIncludes(includes, env, target, source):
    return SCons.PathList.PathList(includes).subst_path(env, target, source)
    

def _generateGUID(slnfile, name):
    """This generates a dummy GUID for the sln file to use.  It is
    based on the MD5 signatures of the sln filename plus the name of
    the project.  It basically just needs to be unique, and not
    change with each invocation."""
    m = hashlib.md5()
    # Normalize the slnfile path to a Windows path (\ separators) so
    # the generated file has a consistent GUID even if we generate
    # it on a non-Windows platform.
    m.update(ntpath.normpath(str(slnfile)) + str(name))
    solution = m.hexdigest().upper()
    # convert most of the signature to GUID form (discard the rest)
    solution = "{" + solution[:8] + "-" + solution[8:12] + "-" + solution[12:16] + "-" + solution[16:20] + "-" + solution[20:32] + "}"
    return solution


def splitFully(path):
    dir, base = os.path.split(path)
    if dir and dir != '' and dir != path:
        return splitFully(dir)+[base]
    if base == '':
        return []
    return [base]

def makeHierarchy(sources):
    '''Break a list of files into a hierarchy; for each value, if it is a string,
       then it is a file.  If it is a dictionary, it is a folder.  The string is
       the original path of the file.'''
    hierarchy = {}
    for file in sources:
        path = splitFully(file)
        if len(path):
            dict = hierarchy
            for part in path[:-1]:
                if (part == '.') or (part == '..'):
                    continue
                if part not in dict:
                    dict[part] = {}
                dict = dict[part]
            dict[path[-1]] = file
        #else:
        #    print 'Warning: failed to decompose path for '+str(file)

    return hierarchy

# NOLA return a file path relative to the project directory
def projectRelativePath(path, projectDir):
    projectDir = SCons.Node.FS.get_default_fs().Dir(projectDir).abspath
    try:
        inputDir = SCons.Node.FS.get_default_fs().Dir(path).abspath
        relDir = os.path.relpath(inputDir, projectDir)
    except:
        inputDir = SCons.Node.FS.get_default_fs().File(path).abspath
        fname = os.path.basename(inputDir)
        inputDir = os.path.dirname(inputDir)
        relDir = os.path.join(os.path.relpath(inputDir, projectDir), fname)
    return relDir


V10DSPHeader = """\
<?xml version="1.0" encoding="%(encoding)s"?>
<Project DefaultTargets="Build" ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
"""

# Release|Win32 etc.
V10DSPProjectConfiguration = """\
\t\t<ProjectConfiguration Include="%(variant)s|%(platform)s">
\t\t\t<Configuration>%(variant)s</Configuration>
\t\t\t<Platform>%(platform)s</Platform>
\t\t</ProjectConfiguration>
"""

V10DSPGlobals = """\
\t<PropertyGroup Label="Globals">
\t\t<ProjectGuid>%(project_guid)s</ProjectGuid>
%(scc_attrs)s\t\t<RootNamespace>%(name)s</RootNamespace>
\t\t<Keyword>MakeFileProj</Keyword>
\t</PropertyGroup>
"""

# VCProjectConfigurationProperties Interface
# http://msdn.microsoft.com/en-us/library/microsoft.visualstudio.vcproject.vcprojectconfigurationproperties.aspx
V10DSPPropertyGroupCondition = """\
\t<PropertyGroup Condition="'$(Configuration)|$(Platform)'=='%(variant)s|%(platform)s'" Label="Configuration">
\t\t<ConfigurationType>%(config_type)s</ConfigurationType>
\t\t<UseOfMfc>false</UseOfMfc>
\t\t<PlatformToolset>%(msvc_version)s</PlatformToolset>
\t</PropertyGroup>
\t<PropertyGroup Condition="'$(Configuration)|$(Platform)'=='%(variant)s|%(platform)s'">
\t\t<IntDir>%(build_dir)s/$(Configuration)/$(ProjectName)/</IntDir>
\t\t<OutDir>%(build_dir)s/$(Configuration)/</OutDir>
\t\t<IncludePath>$(IncludePath)</IncludePath>
\t</PropertyGroup>
"""

V10DSPImportGroupCondition = """\
\t<ImportGroup Condition="'$(Configuration)|$(Platform)'=='%(variant)s|%(platform)s'" Label="PropertySheets">
\t\t<Import Project="$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props" Condition="exists('$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props')" Label="LocalAppDataPlatform" />
\t</ImportGroup>
"""

V10DSPItemDefinition = """\
\t<ItemDefinitionGroup>
\t\t<ClCompile>
\t\t\t<AdditionalIncludeDirectories>%(includepath)s</AdditionalIncludeDirectories>
\t\t<PreprocessorDefinitions>%(cppdefines)s</PreprocessorDefinitions>
\t\t<RuntimeLibrary Condition="'$(Configuration)|$(Platform)'=='Debug|Win32'">MultiThreadedDebugDLL</RuntimeLibrary>
\t\t<RuntimeLibrary Condition="'$(Configuration)|$(Platform)'=='Release|Win32'">MultiThreadedDLL</RuntimeLibrary>
\t\t<Optimization Condition="'$(Configuration)|$(Platform)'=='Debug|Win32'">Disabled</Optimization>
\t\t<MultiProcessorCompilation Condition="'$(Configuration)|$(Platform)'=='Debug|Win32'">true</MultiProcessorCompilation>
\t\t<MultiProcessorCompilation Condition="'$(Configuration)|$(Platform)'=='Release|Win32'">true</MultiProcessorCompilation>
\t\t<WarningLevel Condition="'$(Configuration)|$(Platform)'=='Debug|Win32'">Level3</WarningLevel>
\t\t<WarningLevel Condition="'$(Configuration)|$(Platform)'=='Release|Win32'">Level3</WarningLevel>
\t\t</ClCompile>
\t\t<Link>
\t\t\t<AdditionalLibraryDirectories>$(SolutionDir)%(lib_paths)s%%(AdditionalLibraryDirectories)</AdditionalLibraryDirectories>
\t\t\t<AdditionalDependencies Condition="'$(Configuration)|$(Platform)'=='Debug|Win32'">%(libs_dbg)s%%(AdditionalDependencies)</AdditionalDependencies>
\t\t\t<AdditionalDependencies Condition="'$(Configuration)|$(Platform)'=='Release|Win32'">%(libs_rel)s%%(AdditionalDependencies)</AdditionalDependencies>
\t\t\t<GenerateDebugInformation Condition="'$(Configuration)|$(Platform)'=='Debug|Win32'">true</GenerateDebugInformation>
\t\t</Link>
\t</ItemDefinitionGroup>
"""

class _GenerateVCXProj(_ProjGenerator):
    """Generates a Project file for MSVS 2010"""

    def __init__(self, dspfile, source, env):
        _ProjGenerator.__init__(self, dspfile, source, env)
        
        self.dspheader = V10DSPHeader
        self.dspconfiguration = V10DSPProjectConfiguration
        self.dspglobals = V10DSPGlobals
        self.projectDir = os.path.dirname(str(dspfile))

    def PrintHeader(self):
        env = self.env
        name = self.name
        encoding = env.subst('$MSVSENCODING')
        project_guid = env.get('MSVS_PROJECT_GUID', '')
        scc_provider = env.get('MSVS_SCC_PROVIDER', '')
        scc_project_name = env.get('MSVS_SCC_PROJECT_NAME', '')
        scc_aux_path = env.get('MSVS_SCC_AUX_PATH', '')
        # MSVS_SCC_LOCAL_PATH is kept  for backwards compatibility purpose and should
        # be deprecated as soon as possible.
        scc_local_path_legacy = env.get('MSVS_SCC_LOCAL_PATH', '')
        scc_connection_root = env.get('MSVS_SCC_CONNECTION_ROOT', os.curdir)
        scc_local_path = os.path.relpath(scc_connection_root, os.path.dirname(self.dspabs))
        if not project_guid:
            project_guid = _generateGUID(self.dspfile, '')
        if scc_provider != '':
            scc_attrs = '\t\t<SccProjectName>%s</SccProjectName>\n' % scc_project_name
            if scc_aux_path != '':
                scc_attrs += '\t\t<SccAuxPath>%s</SccAuxPath>\n' % scc_aux_path
            scc_attrs += ('\t\t<SccLocalPath>%s</SccLocalPath>\n'
                          '\t\t<SccProvider>%s</SccProvider>\n' % (scc_local_path, scc_provider))
        elif scc_local_path_legacy != '':
            # This case is kept for backwards compatibility purpose and should
            # be deprecated as soon as possible.
            scc_attrs = ('\t\t<SccProjectName>%s</SccProjectName>\n'
                         '\t\t<SccLocalPath>%s</SccLocalPath>\n' % (scc_project_name, scc_local_path_legacy))
        else:
            self.dspglobals = self.dspglobals.replace('%(scc_attrs)s', '')
            
        self.file.write(self.dspheader % locals())
        
        self.file.write('\t<ItemGroup Label="ProjectConfigurations">\n')
        
        confkeys = sorted(self.configs.keys())
        for kind in confkeys:
            variant = self.configs[kind].variant
            platform = self.configs[kind].platform
            self.file.write(self.dspconfiguration % locals())
        
        self.file.write('\t</ItemGroup>\n')
        
        self.file.write(self.dspglobals % locals())
    
    def PrintProject(self):
        name = self.name
        confkeys = sorted(self.configs.keys())
        try:
            build_dir = self.env['BUILD_DIR']
        except:
            build_dir = "#/build/" + self.env['PLATFORM']
        build_dir = projectRelativePath(build_dir, self.projectDir)
        self.file.write('\t<Import Project="$(VCTargetsPath)\Microsoft.Cpp.Default.props" />\n')
        try:
            msvc_version = self.env['MSVC_PLATFORM_TOOLSET']
        except Exception:
            msvc_version = "v120"
            
        for kind in confkeys:
            variant = self.configs[kind].variant
            platform = self.configs[kind].platform
            config_type = "Makefile"
            buildext = self.configs[kind].buildtarget[-4:]
            if buildext == ".lib":
                config_type = "StaticLibrary"
            elif buildext == ".exe":
                config_type = "Application"
            elif buildext == ".dll":
                config_type = "DynamicLibrary"

            # route .exe's into the northstar/bin dir
            output_dir = variant
            buildtarget = self.env.get('buildtarget', None)
            if buildtarget is not None:
                if buildtarget[-4:].lower() == '.exe':
                    output_dir = "../../bin"

            self.file.write(V10DSPPropertyGroupCondition % locals())

        self.file.write('\t<Import Project="$(VCTargetsPath)\Microsoft.Cpp.props" />\n')
        self.file.write('\t<ImportGroup Label="ExtensionSettings">\n')
        self.file.write('\t</ImportGroup>\n')
        
        for kind in confkeys:
            variant = self.configs[kind].variant
            platform = self.configs[kind].platform
            self.file.write(V10DSPImportGroupCondition % locals())
        
        self.file.write('\t<PropertyGroup Label="UserMacros" />\n')
        
        # V10DSPItemDefinition takes the following arguments...
        #      includepath : <AdditionalIncludeDirectories>            : built from CPPPATH
        #      cppdefines  : <PreprocessorDefinitions>                 : built from CPPDEFINES
        #      lib_paths   : <AdditionalLibraryDirectories>            : built from LIB_PATHS
        #      libs_dbg    : <AdditionalDependencies 'Debug|Win32'>    : built from LIBS_REL
        #      libs_rel    : <AdditionalDependencies 'Release|Win32'>  : built from LIBS_DBG
        includepath = ''
        for file in self.env.get('CPPPATH', []):
            fname = projectRelativePath(file, self.projectDir)
            includepath += fname + ';'
        includepath = xmlify(includepath)
        cppdefines = ''
        for d in self.env.get('CPPDEFINES', []):
            cppdefines += d + ';'        
        lib_paths = ''
        for file in self.env.get('LIB_PATHS', []):
            fname = projectRelativePath(file, self.projectDir)
            lib_paths += fname + ';'
        lib_paths = xmlify(lib_paths)
        libs_rel = ''
        for l in self.env.get('LIBS_REL', []):
            libs_rel += l + '.lib;'
        libs_dbg = ''
        for l in self.env.get('LIBS_DBG', []):
            libs_dbg += l + '.lib;'

        self.file.write(V10DSPItemDefinition % locals())
        
        #filter settings in MSVS 2010 are stored in separate file
        self.filtersabs = self.dspabs + '.filters'
        try:
            self.filters_file = open(self.filtersabs, 'w')
        except IOError, detail:
            raise SCons.Errors.InternalError('Unable to open "' + self.filtersabs + '" for writing:' + str(detail))
            
        self.filters_file.write('<?xml version="1.0" encoding="utf-8"?>\n'
                                '<Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">\n')
                                
        self.PrintSourceFiles()
        
        self.filters_file.write('</Project>')
        self.filters_file.close()
        
        self.file.write('\t<Import Project="$(VCTargetsPath)\Microsoft.Cpp.targets" />\n'
                        '\t<ImportGroup Label="ExtensionTargets">\n'
                        '\t</ImportGroup>\n'
                        '</Project>\n')
                       

    def printFilters(self, hierarchy, name):
        sorteditems = sorted(hierarchy.items(), key = lambda a: a[0].lower())
        
        for key, value in sorteditems:
            if SCons.Util.is_Dict(value):
                filter_name = name + '\\' + key
                self.filters_file.write('\t\t<Filter Include="%s">\n'
                                        '\t\t\t<UniqueIdentifier>%s</UniqueIdentifier>\n'
                                        '\t\t</Filter>\n' % (filter_name, _generateGUID(self.dspabs, filter_name)))
                self.printFilters(value, filter_name)
        
    def printSources(self, hierarchy, kind, commonprefix, filter_name):
        keywords = {'Source Files': 'ClCompile',
                    'Header Files': 'ClInclude',
                    'Local Headers': 'ClInclude',
                    'Resource Files': 'None',
                    'Other Files': 'None'}
                    
        sorteditems = sorted(hierarchy.items(), key = lambda a: a[0].lower())

        # First folders, then files
        for key, value in sorteditems:
            if SCons.Util.is_Dict(value):
                self.printSources(value, kind, commonprefix, filter_name + '\\' + key)

        # redirect the include files to be listed under the source filters
        redirect_filter_name = filter_name
        if kind == 'Header Files' :
            redirect_filter_name = "Source Files" + filter_name[filter_name.find('\\'):]

        for key, value in sorteditems:
            if SCons.Util.is_String(value):
                fs = SCons.Node.FS.get_default_fs()
                file = value
                if commonprefix:
                    file = os.path.join(commonprefix, value)

                if file.find('\\platform\\web\\') != -1:
                    self.file.write('\t\t<%s Include="%s">\n'
                    '\t\t\t<ExcludedFromBuild Condition=\"\'$(Configuration)|$(Platform)\'==\'Debug|Win32\'\">true</ExcludedFromBuild>\n'
                    '\t\t</ClCompile>\n' % (keywords[kind], file))
                else:
                    self.file.write('\t\t<%s Include="%s" />\n' % (keywords[kind], file))

                self.filters_file.write('\t\t<%s Include="%s">\n'
                                        '\t\t\t<Filter>%s</Filter>\n'
                                        '\t\t</%s>\n' % (keywords[kind], file, redirect_filter_name, keywords[kind]))

    def PrintSourceFiles(self):
        categories = {'Source Files': 'cpp;c;cxx;l;y;def;odl;idl;hpj;bat',
                      'Header Files': 'h;hpp;hxx;hm;inl',
                      'Local Headers': 'h;hpp;hxx;hm;inl',
                      'Resource Files': 'r;rc;ico;cur;bmp;dlg;rc2;rct;bin;cnt;rtf;gif;jpg;jpeg;jpe',
                      'Other Files': ''}
        
        cats = sorted([k for k in categories.keys() if self.sources[k]],
                    key = lambda a: a.lower())

        # generate sources lists
        for kind in cats:
            sources = []
            for sfile in self.sources[kind]:
                sfile = projectRelativePath(sfile, self.projectDir)
                sources.append(sfile)
            self.sources[kind] = sources

        # remove include files that do not live alongside source
        local_incs = []
        external_incs = []
        for inc in self.sources['Header Files']:
            incbase = os.path.dirname(inc)
            for src in self.sources['Source Files']:
                srcbase = os.path.dirname(src)
                if incbase == srcbase :
                    local_incs.append(inc)
                    break
            if local_incs and local_incs[-1] != inc:
                # print "[REJECT] INC=["+inc+"]  base=["+incbase+"]"
                external_incs.append(inc)
            self.sources['Header Files'] = list(local_incs)
            
        # print vcxproj.filters file first
        self.filters_file.write('\t<ItemGroup>\n')
        for kind in cats:
        
            # no Header File specific filter catagories
            if kind == 'Header Files' :
                continue

            self.filters_file.write('\t\t<Filter Include="%s">\n'
                                    '\t\t\t<UniqueIdentifier>{7b42d31d-d53c-4868-8b92-ca2bc9fc052f}</UniqueIdentifier>\n'
                                    '\t\t\t<Extensions>%s</Extensions>\n'
                                    '\t\t</Filter>\n' % (kind, categories[kind]))

            hierarchy = makeHierarchy(self.sources[kind])
            self.printFilters(hierarchy, kind)
            
        self.filters_file.write('\t</ItemGroup>\n')
            
        # then print files and filters
        for kind in cats:
            self.file.write('\t<ItemGroup>\n')
            self.filters_file.write('\t<ItemGroup>\n')
                
            # First remove any common prefix
            sources = self.sources[kind]          
            hierarchy = makeHierarchy(sources)

            self.printSources(hierarchy, kind, '', kind)
            self.file.write('\t</ItemGroup>\n')
            self.filters_file.write('\t</ItemGroup>\n')
        
        # establish dependencies to other projects - these show up in Properties/Common Properties/References
        references = self.env.get('project_references', None)
        if references is not None:
            suffix = '.vcxproj'
            self.file.write('\t<ItemGroup>\n')
            for ref in references:
                projname = '%s%s' % (ref, suffix)
                self.file.write('\t\t<ProjectReference Include="%s">\n' % (xmlify(projname),))
                self.file.write('\t\t\t<Project>%s</Project>\n' % (_generateGUID(self.dspfile, ref), ))
                self.file.write('\t\t</ProjectReference>\n')
            self.file.write('\t</ItemGroup>\n')

        # add the SConscript file outside of the groups
        self.file.write('\t<ItemGroup>\n'
                        '\t\t<None Include="%s" />\n'
                        '\t</ItemGroup>\n' % str(self.sconscript))

    def Parse(self):
        print "_GenerateVCXProj.Parse()"

    def Build(self):
        try:
            self.file = open(self.dspabs, 'w')
        except IOError, detail:
            raise SCons.Errors.InternalError('Unable to open "' + self.dspabs + '" for writing:' + str(detail))
        else:
            self.PrintHeader()
            self.PrintProject()
            self.file.close()

def GenerateVCXProject(target, source, env):
    dspfile = target[0]
    if 'MSVS_VERSION' in env:
        version_num, suite = msvs_parse_version(env['MSVS_VERSION'])
    if version_num >= 12.0:
        g = _GenerateVCXProj(dspfile, source, env)
        g.Build()
    else:
        raise SCons.Errors.InternalError("MSVSNativeProject only works for Visual Studio Version 12.0")

