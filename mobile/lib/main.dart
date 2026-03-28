import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:km_marketplace/core/l10n/app_localizations.dart';

import 'app/router.dart';
import 'app/theme.dart';
import 'features/auth/data/auth_state.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const ProviderScope(child: KmMarketplaceApp()));
}

class KmMarketplaceApp extends ConsumerStatefulWidget {
  const KmMarketplaceApp({super.key});

  @override
  ConsumerState<KmMarketplaceApp> createState() => _KmMarketplaceAppState();
}

class _KmMarketplaceAppState extends ConsumerState<KmMarketplaceApp> {
  @override
  void initState() {
    super.initState();
    Future.microtask(() => ref.read(authProvider.notifier).checkAuth());
  }

  @override
  Widget build(BuildContext context) {
    final router = ref.watch(routerProvider);

    return MaterialApp.router(
      debugShowCheckedModeBanner: false,
      title: 'KM Marketplace',
      theme: AppTheme.light,
      routerConfig: router,
      localizationsDelegates: const [
        S.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      supportedLocales: S.supportedLocales,
    );
  }
}
