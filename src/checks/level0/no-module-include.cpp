/*
  This file is part of the clazy static checker.

    Copyright (C) 2023 Johnny Jazeix <jazeix@gmail.com>

    This library is free software; you can redistribute it and/or
    modify it under the terms of the GNU Library General Public
    License as published by the Free Software Foundation; either
    version 2 of the License, or (at your option) any later version.

    This library is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
    Library General Public License for more details.

    You should have received a copy of the GNU Library General Public License
    along with this library; see the file COPYING.LIB.  If not, write to
    the Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor,
    Boston, MA 02110-1301, USA.
*/

#include "no-module-include.h"
#include "ClazyContext.h"
#include "PreProcessorVisitor.h"

#include <clang/Basic/LLVM.h>

#include <vector>

namespace clang
{
class Decl;
} // namespace clang

using namespace clang;

NoModuleInclude::NoModuleInclude(const std::string &name, ClazyContext *context)
    : CheckBase(name, context)
{
    m_modulesList = {"Core", "Gui", "Qml", "QmlModels", "Test", "Network", "DBus", "Quick", "Svg", "Widgets", "Xml", "Concurrent", "Multimedia", "Sql", "PrintSupport"};
    for (const std::string &module : m_modulesList) {
        m_filesToIgnore.emplace_back("Qt" + module + "Depends");
    }
    enablePreProcessorCallbacks();
}

void NoModuleInclude::VisitInclusionDirective(clang::SourceLocation HashLoc,
                                              const clang::Token & /*IncludeTok*/,
                                              clang::StringRef FileName,
                                              bool /*IsAngled*/,
                                              clang::CharSourceRange FilenameRange,
                                              clazy::OptionalFileEntryRef /*File*/,
                                              clang::StringRef /*SearchPath*/,
                                              clang::StringRef /*RelativePath*/,
                                              const clang::Module * /*Imported*/,
                                              clang::SrcMgr::CharacteristicKind /*FileType*/)
{
    if (shouldIgnoreFile(HashLoc)) {
        return;
    }

    for (const std::string &module : m_modulesList) {
        const std::string qtModule = "Qt" + module;
        if (FileName.str() == qtModule + "/" + qtModule || FileName.str() == qtModule) {
            emitWarning(FilenameRange.getAsRange().getBegin(), "Module " + qtModule + " should not be included directly");
        }
    }
}
