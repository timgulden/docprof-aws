import { Outlet, Link, useLocation, useNavigate } from "react-router-dom";
import { MessageSquare, GraduationCap, BookOpen, LogOut } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { useAuthStore } from "../../store/authStore";
import { useChatStore } from "../../store/chatStore";
import { SessionList } from "../chat/SessionList";
import { getTunnelStatus, enableTunnel, disableTunnel } from "../../api/tunnel";

export const Layout = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const authState = useAuthStore((store) => store.state);
  const authDispatch = useAuthStore((store) => store.dispatch);
  const chatState = useChatStore((store) => store.state);
  const queryClient = useQueryClient();
  
  const isChatRoute = location.pathname === "/chat";
  const isSourcesRoute = location.pathname === "/sources";
  const isCourseDetailRoute = /^\/courses\/[^/]+$/.test(location.pathname); // Matches /courses/:courseId

  // Tunnel status query - only succeeds if user is "tim"
  const { data: tunnelStatus, isLoading: tunnelLoading } = useQuery({
    queryKey: ["tunnel-status"],
    queryFn: getTunnelStatus,
    refetchInterval: 5000, // Poll every 5 seconds to keep status updated
    retry: false, // Don't retry on 403 (not tim user) or other errors
  });

  // Tunnel enable/disable mutations
  const enableMutation = useMutation({
    mutationFn: enableTunnel,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tunnel-status"] });
    },
  });

  const disableMutation = useMutation({
    mutationFn: disableTunnel,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tunnel-status"] });
    },
  });

  const handleTunnelToggle = () => {
    if (tunnelStatus?.enabled) {
      disableMutation.mutate();
    } else {
      enableMutation.mutate();
    }
  };

  const navItems = [
    { path: "/sources", label: "Sources", icon: BookOpen },
    { path: "/chat", label: "Chat", icon: MessageSquare },
    { path: "/courses", label: "Courses", icon: GraduationCap },
  ];

  const handleLogout = async () => {
    await authDispatch({ type: "logout_requested" });
    navigate("/login");
  };

  return (
    <div className="min-h-screen bg-slate-100">
      <nav className="border-b bg-white shadow-sm">
        <div className={`${isChatRoute ? "px-4 sm:px-6 lg:px-8" : "mx-auto max-w-7xl px-4 sm:px-6 lg:px-8"} relative`}>
          {/* Main Navigation Row */}
          <div className="flex h-16 items-center justify-between">
            <div className="flex items-center gap-3">
              <picture>
                <source srcSet="/logo-64px-dark.svg" media="(prefers-color-scheme: dark)" />
                <img 
                  src="/logo-64px-light.svg" 
                  alt="DocProf Logo" 
                  className="h-14 w-auto"
                />
              </picture>
              <div className="flex flex-col">
                <h1 className="text-xl font-semibold text-slate-900">M&A Expert</h1>
                {isChatRoute && (
                  <p className="text-sm text-slate-500">
                    {chatState.uiMessage ?? "Ask anything about valuation or M&A."}
                  </p>
                )}
              </div>
              {/* Tunnel Toggle Switch - only shows on Sources screen and if user is "tim" (query succeeds) */}
              {isSourcesRoute && tunnelStatus !== undefined && (
                <>
                  <div className="w-12"></div>
                  <div className="flex flex-col items-start">
                  <div className="flex items-center gap-2">
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={tunnelStatus.enabled}
                        onChange={handleTunnelToggle}
                        disabled={tunnelLoading || enableMutation.isPending || disableMutation.isPending}
                        className="sr-only peer"
                      />
                      <div className="w-11 h-6 bg-slate-300 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-500 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                    </label>
                    <span className="text-xs font-medium text-slate-700">
                      Internet Access: {tunnelStatus.enabled ? "On" : "Off"}
                    </span>
                  </div>
                  {tunnelStatus.enabled && tunnelStatus.frontend_url && (
                    <span className="mt-0.5 text-[10px] text-slate-500">
                      {tunnelStatus.frontend_url.replace("https://", "")}
                    </span>
                  )}
                  </div>
                </>
              )}
            </div>
            {/* Centered Sessions Button - Only on Chat Route */}
            {isChatRoute && (
              <div className="absolute left-1/2 -translate-x-1/2">
                <SessionList.Button />
              </div>
            )}
            <div className="flex items-center space-x-4">
              <div className="flex space-x-1">
                {navItems.map((item) => {
                  const Icon = item.icon;
                  // For courses, also highlight when on course detail pages or new course page
                  // For sources, highlight when on sources page
                  const isActive = item.path === "/courses" 
                    ? location.pathname.startsWith("/courses")
                    : item.path === "/sources"
                    ? location.pathname.startsWith("/sources")
                    : location.pathname === item.path;
                  return (
                    <Link
                      key={item.path}
                      to={item.path}
                      className={`flex items-center space-x-2 rounded-md px-4 py-2 text-sm font-medium transition-colors ${
                        isActive
                          ? "bg-blue-600 text-white"
                          : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                      }`}
                    >
                      <Icon size={18} />
                      <span>{item.label}</span>
                    </Link>
                  );
                })}
              </div>
              {authState.user ? (
                <div className="flex items-center space-x-3 border-l pl-4">
                  <span className="text-sm text-slate-600">{authState.user.username}</span>
                  <button
                    onClick={handleLogout}
                    className="flex items-center space-x-1 rounded-md px-3 py-1.5 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900"
                  >
                    <LogOut size={16} />
                    <span>Logout</span>
                  </button>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </nav>
      {isChatRoute && <SessionList />}
      <main className={
        isChatRoute || isCourseDetailRoute 
          ? "h-[calc(100vh-4rem)]" 
          : "mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-6"
      }>
        <Outlet />
      </main>
    </div>
  );
};

