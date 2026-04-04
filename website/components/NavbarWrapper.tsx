import { usePathname } from "next/navigation";
import { CleanNavigation } from "./Navbar";

interface NavbarWrapperProps {
  className?: string;
}

export const NavbarWrapper = ({ className }: NavbarWrapperProps) => {
  const pathname = usePathname();

  // Hide navbar on dashboard routes
  if (pathname.startsWith("/dashboard")) {
    return null;
  }

  return <CleanNavigation className={className} />;
};

export default NavbarWrapper;