import { Link, useNavigate } from "@tanstack/react-router";
import { LogOut, User as UserIcon, Aperture } from "lucide-react";
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

  const handleLogout = () => {
    signOut();
    navigate({ to: "/" });
  };

  return (
    <header className="sticky top-0 z-40 border-b border-border/60 bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5">
        <div className="flex items-center gap-6">
          {user ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  aria-label="Profile"
                  className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-sunset text-primary-foreground shadow-soft transition-transform hover:scale-105"
                >
                  <span className="text-sm font-medium">
                    {user.name.charAt(0).toUpperCase()}
                  </span>
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
                  <Link to="/dashboard" className="cursor-pointer">Dashboard</Link>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <Link to="/query" className="cursor-pointer">Find by photo</Link>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <Link to="/" className="flex items-center gap-2">
              <Aperture className="h-5 w-5 text-primary" />
              <span className="font-serif text-xl">Atelier</span>
            </Link>
          )}

          {showNav && user && (
            <nav className="hidden items-center gap-5 text-sm md:flex">
              <Link
                to="/dashboard"
                activeProps={{ className: "text-foreground" }}
                className="text-muted-foreground transition-colors hover:text-foreground"
              >
                Upload
              </Link>
              <Link
                to="/query"
                activeProps={{ className: "text-foreground" }}
                className="text-muted-foreground transition-colors hover:text-foreground"
              >
                Find by photo
              </Link>
              <Link
                to="/about"
                activeProps={{ className: "text-foreground" }}
                className="text-muted-foreground transition-colors hover:text-foreground"
              >
                About
              </Link>
            </nav>
          )}
        </div>

        <div className="flex items-center gap-2">
          {user ? (
            <Button variant="ghost" size="sm" onClick={handleLogout}>
              <LogOut className="mr-2 h-4 w-4" />
              Logout
            </Button>
          ) : (
            <>
              <Link to="/about" className="hidden text-sm text-muted-foreground hover:text-foreground md:inline">
                About
              </Link>
              <Button asChild size="sm" variant="outline">
                <Link to="/">
                  <UserIcon className="mr-2 h-4 w-4" />
                  Sign in
                </Link>
              </Button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
