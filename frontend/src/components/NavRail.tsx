import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  Layers,
  Search,
  FlaskConical,
  BookMarked,
  IndianRupee,
  RefreshCw,
  Settings,
  BookOpen,
} from 'lucide-react';

interface NavItem {
  to: string;
  match: string; // prefix for active detection
  label: string;
  Icon: React.FC<{ className?: string }>;
}

const PRIMARY: NavItem[] = [
  { to: '/research',  match: '/research',  label: 'Research',  Icon: Layers        },
  { to: '/discover',  match: '/discover',  label: 'Discover',  Icon: Search        },
  { to: '/validate',  match: '/validate',  label: 'Validate',  Icon: FlaskConical  },
  { to: '/trade',     match: '/trade',     label: 'Trade',     Icon: BookMarked    },
  { to: '/portfolio', match: '/portfolio', label: 'Portfolio', Icon: IndianRupee   },
];

const UTILITY: NavItem[] = [
  { to: '/sync',     match: '/sync',     label: 'Sync',     Icon: RefreshCw },
  { to: '/settings', match: '/settings', label: 'Settings', Icon: Settings  },
  { to: '/about',    match: '/about',    label: 'About',    Icon: BookOpen  },
];

function RailItem({ to, match, label, Icon }: NavItem) {
  const { pathname } = useLocation();
  const isActive = pathname === match || pathname.startsWith(match + '/');

  return (
    <NavLink
      to={to}
      title={label}
      className={`flex flex-col items-center gap-0.5 py-2.5 px-1 rounded-lg transition-all duration-150 cursor-pointer w-full ${
        isActive
          ? 'bg-accent-primary/15 text-accent-primary'
          : 'text-text-muted hover:text-text-main hover:bg-bg-surface/70'
      }`}
    >
      <Icon className="w-4 h-4 shrink-0" />
      <span className={`text-[9px] font-bold tracking-wide leading-none ${isActive ? 'text-accent-primary' : ''}`}>
        {label}
      </span>
    </NavLink>
  );
}

export const NavRail: React.FC = () => (
  <nav className="w-14 shrink-0 flex flex-col items-center py-2 gap-0.5 border-r border-border-subtle bg-bg-surface/60 overflow-y-auto">
    {PRIMARY.map(item => (
      <RailItem key={item.to} {...item} />
    ))}

    <div className="my-1 w-8 border-t border-border-subtle/50" />

    {UTILITY.map(item => (
      <RailItem key={item.to} {...item} />
    ))}
  </nav>
);
