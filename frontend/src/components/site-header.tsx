import { Link, useNavigate } from "@tanstack/react-router";
import { LogOut, ScanFace } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { signOut } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export function SiteHeader({ showNav = true }: { showNav?: boolean }) {
  const { user } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await signOut();
    navigate({ to: "/" });
  };

  return (
    <header className="sticky top-0 z-40 border-b border-foreground/15 bg-background/90 backdrop-blur-xl supports-[backdrop-filter]:bg-background/80">
      <div className="mx-auto flex h-[4.5rem] max-w-[90rem] items-center justify-between px-5 sm:px-8">
        <div className="flex items-center gap-6">
          {user ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  aria-label="Profile"
                  className="flex h-10 w-10 items-center justify-center rounded-full bg-foreground text-background transition-transform hover:scale-105"
                >
                  <span className="text-sm font-medium">{user.name.charAt(0).toUpperCase()}</span>
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="w-56">
                <DropdownMenuLabel>
                  <div className="flex flex-col">
                    <span className="font-serif text-base">{user.name}</span>
                    <span className="text-xs text-muted-foreground">{user.email}</span>
                  </div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild>
                  <Link to="/dashboard" className="cursor-pointer">
                    Dashboard
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <Link to="/query" className="cursor-pointer">
                    Find by photo
                  </Link>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <Link to="/" className="flex items-center gap-2.5" aria-label="FaceSeek home">
              <ScanFace className="h-5 w-5 text-primary" strokeWidth={1.7} />
              <span className="text-sm font-bold uppercase tracking-[0.13em]">FaceSeek</span>
            </Link>
          )}

          {showNav && (
            <nav className="hidden items-center gap-7 text-sm font-medium sm:flex">
              {user ? (
                <>
                  <Link
                    to="/dashboard"
                    activeProps={{ className: "text-primary" }}
                    className="text-muted-foreground transition-colors hover:text-foreground"
                  >
                    Upload
                  </Link>
                  <Link
                    to="/query"
                    activeProps={{ className: "text-primary" }}
                    className="text-muted-foreground transition-colors hover:text-foreground"
                  >
                    Find by photo
                  </Link>
                  <Link
                    to="/about"
                    activeProps={{ className: "text-primary" }}
                    className="text-muted-foreground transition-colors hover:text-foreground"
                  >
                    About
                  </Link>
                </>
              ) : (
                <>
                  <Link
                    to="/"
                    activeOptions={{ exact: true }}
                    activeProps={{ className: "text-primary" }}
                    className="text-muted-foreground transition-colors hover:text-foreground"
                  >
                    Home
                  </Link>
                  <Link
                    to="/demo"
                    activeProps={{ className: "text-primary" }}
                    className="text-muted-foreground transition-colors hover:text-foreground"
                  >
                    Demo
                  </Link>
                  <Link
                    to="/about"
                    activeProps={{ className: "text-primary" }}
                    className="text-muted-foreground transition-colors hover:text-foreground"
                  >
                    About
                  </Link>
                </>
              )}
            </nav>
          )}
        </div>

        {user && (
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={handleLogout}>
              <LogOut className="mr-2 h-4 w-4" />
              Logout
            </Button>
          </div>
        )}
      </div>
    </header>
  );
}
