import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _preferredLocaleKey = 'preferred_locale_code';

class LocaleController extends StateNotifier<Locale?> {
  LocaleController() : super(null);

  Future<void> load() async {
    final prefs = await SharedPreferences.getInstance();
    final savedCode = prefs.getString(_preferredLocaleKey);
    final nextLocale = _normalizeLocale(savedCode);
    if (state == nextLocale) {
      return;
    }
    state = nextLocale;
  }

  Future<void> setLocaleByCode(String? languageCode) async {
    final nextLocale = _normalizeLocale(languageCode);

    if (state == nextLocale) {
      return;
    }

    final prefs = await SharedPreferences.getInstance();
    if (nextLocale == null) {
      await prefs.remove(_preferredLocaleKey);
    } else {
      await prefs.setString(_preferredLocaleKey, nextLocale.languageCode);
    }

    state = nextLocale;
  }

  Locale? _normalizeLocale(String? languageCode) {
    if (languageCode == null || languageCode.trim().isEmpty) {
      return null;
    }

    final normalized = languageCode.toLowerCase();
    if (normalized.startsWith('ru')) {
      return const Locale('ru');
    }
    if (normalized.startsWith('en')) {
      return const Locale('en');
    }

    return null;
  }
}

final localeControllerProvider =
    StateNotifierProvider<LocaleController, Locale?>((ref) {
      return LocaleController();
    });
