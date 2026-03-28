import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:km_marketplace/core/l10n/app_localizations.dart';

import '../../../app/theme.dart';
import '../data/auth_repository.dart';
import '../data/auth_state.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _emailCtrl = TextEditingController();
  final _passwordCtrl = TextEditingController();
  bool _loading = false;
  String? _error;

  @override
  void dispose() {
    _emailCtrl.dispose();
    _passwordCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() { _loading = true; _error = null; });

    try {
      final result = await ref.read(authRepositoryProvider).login(
        email: _emailCtrl.text.trim(),
        password: _passwordCtrl.text,
      );

      await ref.read(authProvider.notifier).setAuthenticated(
        accessToken: result['access_token'] as String,
        refreshToken: result['refresh_token'] as String,
      );
    } on DioException catch (e) {
      final detail = e.response?.data;
      String message = 'Login failed';
      if (detail is Map && detail['detail'] != null) {
        message = detail['detail'].toString();
      }
      setState(() { _error = message; });
    } finally {
      if (mounted) setState(() { _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = S.of(context)!;

    return Scaffold(
      backgroundColor: AppTheme.bgPage,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: Form(
              key: _formKey,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Icon(Icons.apartment_rounded, size: 64, color: AppTheme.accent),
                  const SizedBox(height: 16),
                  Text(
                    l.login,
                    style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w700),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 6),
                  Text(
                    l.loginSubtitle,
                    style: const TextStyle(color: AppTheme.textSubtle, fontSize: 14),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 32),

                  if (_error != null) ...[
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: AppTheme.statusErrorBg,
                        borderRadius: BorderRadius.circular(AppTheme.radius),
                        border: Border.all(color: const Color(0xFFB80000)),
                      ),
                      child: Text(_error!, style: const TextStyle(color: AppTheme.statusError, fontSize: 13)),
                    ),
                    const SizedBox(height: 16),
                  ],

                  TextFormField(
                    controller: _emailCtrl,
                    keyboardType: TextInputType.emailAddress,
                    textInputAction: TextInputAction.next,
                    decoration: InputDecoration(labelText: l.email),
                    validator: (v) {
                      if (v == null || v.trim().isEmpty) return l.fieldRequired;
                      if (!v.contains('@')) return l.invalidEmail;
                      return null;
                    },
                  ),
                  const SizedBox(height: 14),
                  TextFormField(
                    controller: _passwordCtrl,
                    obscureText: true,
                    textInputAction: TextInputAction.done,
                    decoration: InputDecoration(labelText: l.password),
                    validator: (v) {
                      if (v == null || v.isEmpty) return l.fieldRequired;
                      if (v.length < 8) return l.passwordTooShort;
                      return null;
                    },
                    onFieldSubmitted: (_) => _submit(),
                  ),
                  const SizedBox(height: 8),
                  Align(
                    alignment: Alignment.centerRight,
                    child: TextButton(
                      onPressed: () {/* TODO: forgot password screen */},
                      child: Text(l.forgotPassword),
                    ),
                  ),
                  const SizedBox(height: 8),
                  ElevatedButton(
                    onPressed: _loading ? null : _submit,
                    child: _loading
                        ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                        : Text(l.login),
                  ),
                  const SizedBox(height: 16),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(l.noAccount, style: const TextStyle(color: AppTheme.textSubtle, fontSize: 14)),
                      TextButton(
                        onPressed: () => context.go('/register'),
                        child: Text(l.register),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
