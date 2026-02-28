"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { LogOut, BookOpen, User as UserIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import AuthDialog from "@/components/AuthDialog";
import { logout } from "@/lib/auth";
import type { User } from "@/types/auth";

interface UserMenuProps {
  user: User | null;
  onUserChange: (user: User | null) => void;
}

export default function UserMenu({ user, onUserChange }: UserMenuProps) {
  const router = useRouter();
  const [authOpen, setAuthOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  const handleLogout = () => {
    logout();
    onUserChange(null);
    setMenuOpen(false);
  };

  if (!user) {
    return (
      <>
        <Button variant="outline" size="sm" onClick={() => setAuthOpen(true)}>
          <UserIcon className="mr-1.5 h-3.5 w-3.5" />
          로그인
        </Button>
        <AuthDialog
          open={authOpen}
          onOpenChange={setAuthOpen}
          onSuccess={(u) => onUserChange(u)}
        />
      </>
    );
  }

  // Logged-in state: simple inline menu without dropdown-menu dependency
  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setMenuOpen((p) => !p)}
        className="flex items-center gap-2 rounded-md border bg-card px-3 py-1.5 text-sm font-medium transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-expanded={menuOpen}
        aria-haspopup="true"
      >
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">
          {user.name.charAt(0).toUpperCase()}
        </span>
        <span className="max-w-[100px] truncate">{user.name}</span>
      </button>

      {menuOpen && (
        <>
          {/* Backdrop to close on outside click */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setMenuOpen(false)}
            aria-hidden="true"
          />
          <div className="absolute right-0 z-50 mt-2 w-44 rounded-md border bg-popover p-1 shadow-md">
            <div className="px-2 py-1.5 text-xs text-muted-foreground border-b mb-1">
              {user.email}
            </div>
            <button
              type="button"
              className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-accent transition-colors"
              onClick={() => {
                setMenuOpen(false);
                router.push("/exams");
              }}
            >
              <BookOpen className="h-3.5 w-3.5" />
              내 시험지
            </button>
            <button
              type="button"
              className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm text-destructive hover:bg-destructive/10 transition-colors"
              onClick={handleLogout}
            >
              <LogOut className="h-3.5 w-3.5" />
              로그아웃
            </button>
          </div>
        </>
      )}
    </div>
  );
}
