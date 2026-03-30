import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:km_marketplace/core/l10n/app_localizations.dart';

import '../../../../app/theme.dart';

class GuestAuthPrompt extends StatelessWidget {
  const GuestAuthPrompt({
    super.key,
    required this.title,
    required this.message,
    this.icon = Icons.lock_outline,
  });

  final String title;
  final String message;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final l = S.of(context)!;

    return Center(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Container(
          width: 420,
          padding: const EdgeInsets.all(18),
          decoration: BoxDecoration(
            color: AppTheme.bgSurface,
            borderRadius: BorderRadius.circular(AppTheme.cardRadius),
            border: Border.all(color: AppTheme.border),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: 34, color: AppTheme.accent),
              const SizedBox(height: 10),
              Text(
                title,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                message,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontSize: 14,
                  color: AppTheme.textSubtle,
                  height: 1.35,
                ),
              ),
              const SizedBox(height: 14),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () => context.go('/login'),
                      child: Text(l.login),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: () => context.go('/register'),
                      child: Text(l.register),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
