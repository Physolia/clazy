/*
  This file is part of the clazy static checker.

    Copyright (C) 2016 Sergio Martins <smartins@kde.org>
    Copyright (C) 2016 Klarälvdalens Datakonsult AB, a KDAB Group company, info@kdab.coms

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

#include "connect-non-signal.h"
#include "AccessSpecifierManager.h"
#include "ClazyContext.h"
#include "QtUtils.h"
#include "SourceCompatibilityHelpers.h"

#include <clang/AST/Decl.h>
#include <clang/AST/DeclCXX.h>
#include <clang/AST/Expr.h>
#include <clang/AST/Stmt.h>
#include <clang/Basic/LLVM.h>
#include <llvm/Support/Casting.h>

using namespace clang;

ConnectNonSignal::ConnectNonSignal(const std::string &name, ClazyContext *context)
    : CheckBase(name, context, Option_CanIgnoreIncludes)
{
    context->enableAccessSpecifierManager();
}

void ConnectNonSignal::VisitStmt(clang::Stmt *stmt)
{
    auto *call = dyn_cast<CallExpr>(stmt);
    if (!call) {
        return;
    }

    FunctionDecl *func = call->getDirectCallee();
    if (!clazy::isConnect(func) || !clazy::connectHasPMFStyle(func)) {
        return;
    }

    CXXMethodDecl *method = clazy::pmfFromConnect(call, /*argIndex=*/1);
    if (!method) {
        if (clazy::isQMetaMethod(call, 1)) {
            return;
        }
        emitWarning(clazy::getLocStart(call), "couldn't find method from pmf connect, please report a bug");
        return;
    }

    AccessSpecifierManager *accessSpecifierManager = m_context->accessSpecifierManager;
    if (!accessSpecifierManager) {
        return;
    }

    QtAccessSpecifierType qst = accessSpecifierManager->qtAccessSpecifierType(method);
    if (qst != QtAccessSpecifier_Unknown && qst != QtAccessSpecifier_Signal) {
        emitWarning(call, method->getQualifiedNameAsString() + std::string(" is not a signal"));
    }
}
