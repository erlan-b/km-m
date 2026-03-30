import 'package:go_router/go_router.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../features/auth/data/auth_state.dart';
import '../features/auth/presentation/login_screen.dart';
import '../features/auth/presentation/register_screen.dart';
import '../features/chat/presentation/chat_detail_screen.dart';
import '../features/chat/presentation/conversations_screen.dart';
import '../features/favorites/presentation/favorites_screen.dart';
import '../features/home/presentation/home_feed_screen.dart';
import '../features/home/presentation/home_shell.dart';
import '../features/listings/presentation/listing_form_screen.dart';
import '../features/listings/presentation/listing_detail_screen.dart';
import '../features/listings/presentation/my_listings_screen.dart';
import '../features/listings/presentation/owner_profile_screen.dart';
import '../features/notifications/presentation/notifications_screen.dart';
import '../features/payments/presentation/payment_history_screen.dart';
import '../features/profile/presentation/profile_screen.dart';
import '../features/promotions/presentation/my_promotions_screen.dart';
import '../features/promotions/presentation/promote_listing_screen.dart';

final routerProvider = Provider<GoRouter>((ref) {
  final authState = ref.watch(authProvider);

  return GoRouter(
    initialLocation: '/home',
    redirect: (context, state) {
      final isAuth = authState.isAuthenticated;
      final location = state.matchedLocation;
      final isAuthRoute = location == '/login' || location == '/register';

      final requiresAuth =
          location.startsWith('/notifications') ||
          location.startsWith('/my-listings') ||
          location.startsWith('/my-promotions') ||
          location.startsWith('/payments') ||
          location.startsWith('/chat/') ||
          location.startsWith('/promote/');

      if (authState.status == AuthStatus.unknown) return null;

      if (!isAuth && requiresAuth) return '/login';
      if (isAuth && isAuthRoute) return '/home';

      return null;
    },
    routes: [
      GoRoute(path: '/login', builder: (context, state) => const LoginScreen()),
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
      GoRoute(
        path: '/chat/:id',
        builder: (context, state) {
          final id = int.parse(state.pathParameters['id']!);
          final extra = state.extra;
          final initialConversation = extra is Map
              ? Map<String, dynamic>.from(extra)
              : null;
          return ChatDetailScreen(
            conversationId: id,
            initialConversation: initialConversation,
          );
        },
      ),
      GoRoute(
        path: '/notifications',
        builder: (context, state) => const NotificationsScreen(),
      ),
      GoRoute(
        path: '/promote/:listingId',
        builder: (context, state) {
          final listingId = int.parse(state.pathParameters['listingId']!);
          final extra = state.extra;
          final initialListing = extra is Map
              ? Map<String, dynamic>.from(extra)
              : null;

          return PromoteListingScreen(
            listingId: listingId,
            initialListing: initialListing,
          );
        },
      ),
      GoRoute(
        path: '/my-promotions',
        builder: (context, state) => const MyPromotionsScreen(),
      ),
      GoRoute(
        path: '/payments',
        builder: (context, state) => const PaymentHistoryScreen(),
      ),
      GoRoute(
        path: '/my-listings',
        builder: (context, state) => const MyListingsScreen(),
      ),
      GoRoute(
        path: '/my-listings/create',
        builder: (context, state) => const ListingFormScreen(),
      ),
      GoRoute(
        path: '/my-listings/:id/edit',
        builder: (context, state) {
          final id = int.parse(state.pathParameters['id']!);
          final extra = state.extra;
          final initialListing = extra is Map
              ? Map<String, dynamic>.from(extra)
              : null;
          return ListingFormScreen(
            listingId: id,
            initialListing: initialListing,
          );
        },
      ),

      // Main shell with bottom nav
      ShellRoute(
        builder: (context, state, child) => HomeShell(child: child),
        routes: [
          GoRoute(
            path: '/home',
            pageBuilder: (context, state) =>
                const NoTransitionPage(child: HomeFeedScreen()),
          ),
          GoRoute(
            path: '/search',
            pageBuilder: (context, state) =>
                const NoTransitionPage(child: HomeFeedScreen()),
          ),
          GoRoute(
            path: '/favorites',
            pageBuilder: (context, state) =>
                const NoTransitionPage(child: FavoritesScreen()),
          ),
          GoRoute(
            path: '/inbox',
            pageBuilder: (context, state) =>
                const NoTransitionPage(child: ConversationsScreen()),
          ),
          GoRoute(
            path: '/profile',
            pageBuilder: (context, state) =>
                const NoTransitionPage(child: ProfileScreen()),
          ),
        ],
      ),
    ],
  );
});
