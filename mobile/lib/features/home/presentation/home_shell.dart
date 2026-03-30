import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:km_marketplace/core/l10n/app_localizations.dart';

import '../../../app/theme.dart';

class HomeShell extends StatelessWidget {
  const HomeShell({super.key, required this.child});

  final Widget child;

  int _currentIndex(BuildContext context) {
    final location = GoRouterState.of(context).matchedLocation;
    if (location.startsWith('/home') || location.startsWith('/search')) {
      return 0;
    }
    if (location.startsWith('/favorites')) return 1;
    if (location.startsWith('/inbox')) return 2;
    if (location.startsWith('/profile')) return 3;
    return 0;
  }

  void _onTap(BuildContext context, int index) {
    switch (index) {
      case 0:
        context.go('/home');
        return;
      case 1:
        context.go('/favorites');
        return;
      case 2:
        context.go('/inbox');
        return;
      case 3:
        context.go('/profile');
        return;
      default:
        return;
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = S.of(context)!;
    final idx = _currentIndex(context);

    return Scaffold(
      body: child,
      bottomNavigationBar: Container(
        decoration: const BoxDecoration(
          border: Border(top: BorderSide(color: AppTheme.border)),
        ),
        child: BottomNavigationBar(
          currentIndex: idx,
          onTap: (i) => _onTap(context, i),
          items: [
            BottomNavigationBarItem(
              icon: const Icon(Icons.home_outlined),
              activeIcon: const Icon(Icons.home),
              label: l.navHome,
            ),
            BottomNavigationBarItem(
              icon: const Icon(Icons.bookmark_border),
              activeIcon: const Icon(Icons.bookmark),
              label: l.navFavorites,
            ),
            BottomNavigationBarItem(
              icon: const Icon(Icons.chat_bubble_outline),
              activeIcon: const Icon(Icons.chat_bubble),
              label: l.conversations,
            ),
            BottomNavigationBarItem(
              icon: const Icon(Icons.person_outline),
              activeIcon: const Icon(Icons.person),
              label: l.navProfile,
            ),
          ],
        ),
      ),
    );
  }
}
