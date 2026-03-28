import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../features/auth/data/auth_state.dart';
import '../features/auth/presentation/login_screen.dart';
import '../features/auth/presentation/register_screen.dart';
import '../features/home/presentation/home_feed_screen.dart';
import '../features/home/presentation/home_shell.dart';
import '../features/listings/presentation/listing_detail_screen.dart';
import '../features/listings/presentation/owner_profile_screen.dart';
import '../features/search/presentation/search_screen.dart';

final routerProvider = Provider<GoRouter>((ref) {
  final authState = ref.watch(authProvider);

  return GoRouter(
    initialLocation: '/home',
    redirect: (context, state) {
      final isAuth = authState.isAuthenticated;
      final isAuthRoute = state.matchedLocation == '/login' || state.matchedLocation == '/register';

      if (authState.status == AuthStatus.unknown) return null;

      if (!isAuth && !isAuthRoute) return '/login';
      if (isAuth && isAuthRoute) return '/home';

      return null;
    },
    routes: [
      GoRoute(
        path: '/login',
        builder: (context, state) => const LoginScreen(),
      ),
      GoRoute(
        path: '/register',
        builder: (context, state) => const RegisterScreen(),
      ),

      // Detail routes (outside shell — no bottom nav)
      GoRoute(
        path: '/listing/:id',
        builder: (context, state) {
          final id = int.parse(state.pathParameters['id']!);
          return ListingDetailScreen(listingId: id);
        },
      ),
      GoRoute(
        path: '/owner/:id',
        builder: (context, state) {
          final id = int.parse(state.pathParameters['id']!);
          return OwnerProfileScreen(userId: id);
        },
      ),

      // Main shell with bottom nav
      ShellRoute(
        builder: (context, state, child) => HomeShell(child: child),
        routes: [
          GoRoute(
            path: '/home',
            pageBuilder: (context, state) => const NoTransitionPage(child: HomeFeedScreen()),
          ),
          GoRoute(
            path: '/search',
            pageBuilder: (context, state) => const NoTransitionPage(child: SearchScreen()),
          ),
          GoRoute(
            path: '/favorites',
            pageBuilder: (context, state) => const NoTransitionPage(child: Placeholder()),
          ),
          GoRoute(
            path: '/inbox',
            pageBuilder: (context, state) => const NoTransitionPage(child: Placeholder()),
          ),
          GoRoute(
            path: '/profile',
            pageBuilder: (context, state) => const NoTransitionPage(child: Placeholder()),
          ),
        ],
      ),
    ],
  );
});
