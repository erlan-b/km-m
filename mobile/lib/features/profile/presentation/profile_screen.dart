import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:km_marketplace/core/l10n/app_localizations.dart';
import 'package:km_marketplace/core/l10n/locale_controller.dart';

import '../../../app/theme.dart';
import '../../../core/storage/secure_storage.dart';
import '../../auth/data/auth_repository.dart';
import '../../auth/data/auth_state.dart';
import '../data/profile_repository.dart';

class ProfileScreen extends ConsumerStatefulWidget {
  const ProfileScreen({super.key});

  @override
  ConsumerState<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends ConsumerState<ProfileScreen> {
  bool _loading = true;
  bool _saving = false;
  String? _error;
  Map<String, dynamic>? _me;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final me = await ref.read(profileRepositoryProvider).getMyProfile();
      await ref
          .read(localeControllerProvider.notifier)
          .setLocaleByCode(me['preferred_language']?.toString());
      if (!mounted) {
        return;
      }
      setState(() {
        _me = me;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  String _friendlyError(Object error, S l) {
    if (error is DioException) {
      final data = error.response?.data;
      if (data is Map && data['detail'] is String) {
        return data['detail'].toString();
      }
      if (error.message != null && error.message!.trim().isNotEmpty) {
        return error.message!;
      }
    }
    return l.errorOccurred;
  }

  Future<void> _pickAvatar() async {
    if (_saving) {
      return;
    }

    final l = S.of(context)!;
    final picker = ImagePicker();
    final picked = await picker.pickImage(
      source: ImageSource.gallery,
      imageQuality: 86,
    );
    if (picked == null) {
      return;
    }

    setState(() {
      _saving = true;
    });

    try {
      final updated = await ref
          .read(profileRepositoryProvider)
          .uploadAvatar(picked.path);
      if (!mounted) {
        return;
      }

      setState(() {
        _me = updated;
      });

      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(l.profileUpdated)));
    } catch (e) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(_friendlyError(e, l))));
    } finally {
      if (mounted) {
        setState(() {
          _saving = false;
        });
      }
    }
  }

  Future<void> _showEditProfileSheet() async {
    final me = _me;
    if (me == null || _saving) {
      return;
    }

    final draft = await showModalBottomSheet<_ProfileUpdateDraft>(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (sheetContext) {
        return _EditProfileSheet(initialProfile: me);
      },
    );

    if (draft == null) {
      return;
    }

    if (!mounted) {
      return;
    }

    final l = S.of(context)!;
    setState(() {
      _saving = true;
    });

    try {
      final updated = await ref
          .read(profileRepositoryProvider)
          .updateProfile(draft.toPayload());

      if (!mounted) {
        return;
      }

      setState(() {
        _me = updated;
      });

      await ref
          .read(localeControllerProvider.notifier)
          .setLocaleByCode(draft.preferredLanguage);

      if (!mounted) {
        return;
      }

      ScaffoldMessenger.maybeOf(
        context,
      )?.showSnackBar(SnackBar(content: Text(S.of(context)!.profileUpdated)));
    } catch (e) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.maybeOf(
        context,
      )?.showSnackBar(SnackBar(content: Text(_friendlyError(e, l))));
    } finally {
      if (mounted) {
        setState(() {
          _saving = false;
        });
      }
    }
  }

  Future<void> _logout() async {
    final storage = ref.read(secureStorageProvider);
    final refreshToken = await storage.readRefreshToken();

    if (refreshToken != null && refreshToken.isNotEmpty) {
      try {
        await ref.read(authRepositoryProvider).logout(refreshToken);
      } catch (_) {}
    }

    await ref.read(authProvider.notifier).logout();
    if (!mounted) return;
    context.go('/login');
  }

  @override
  Widget build(BuildContext context) {
    final l = S.of(context)!;

    if (_loading) {
      return Scaffold(
        appBar: AppBar(title: Text(l.profile)),
        body: const Center(
          child: CircularProgressIndicator(color: AppTheme.accent),
        ),
      );
    }

    if (_error != null || _me == null) {
      return Scaffold(
        appBar: AppBar(title: Text(l.profile)),
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(
                Icons.error_outline,
                size: 48,
                color: AppTheme.textSubtle,
              ),
              const SizedBox(height: 12),
              Text(l.errorOccurred),
              const SizedBox(height: 12),
              ElevatedButton(onPressed: _load, child: Text(l.retry)),
            ],
          ),
        ),
      );
    }

    final me = _me!;
    final displayName = me['full_name'] as String? ?? '-';
    final email = me['email'] as String? ?? '-';
    final city = me['city'] as String?;
    final profileImagePath = me['profile_image_url']?.toString();
    final profileImageUrl =
        (profileImagePath == null || profileImagePath.isEmpty)
        ? null
        : ref
              .read(profileRepositoryProvider)
              .absoluteMediaUrl(profileImagePath);

    return Scaffold(
      appBar: AppBar(title: Text(l.profile)),
      body: RefreshIndicator(
        onRefresh: _load,
        color: AppTheme.accent,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
          children: [
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppTheme.bgSurface,
                borderRadius: BorderRadius.circular(AppTheme.cardRadius),
                border: Border.all(color: AppTheme.border),
              ),
              child: Row(
                children: [
                  Stack(
                    clipBehavior: Clip.none,
                    children: [
                      CircleAvatar(
                        radius: 28,
                        backgroundColor: AppTheme.accent,
                        backgroundImage: profileImageUrl == null
                            ? null
                            : NetworkImage(profileImageUrl),
                        child: profileImageUrl != null
                            ? null
                            : Text(
                                displayName.isNotEmpty
                                    ? displayName[0].toUpperCase()
                                    : '?',
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontSize: 22,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                      ),
                      Positioned(
                        right: -6,
                        bottom: -6,
                        child: Material(
                          color: AppTheme.accent,
                          shape: const CircleBorder(),
                          child: InkWell(
                            customBorder: const CircleBorder(),
                            onTap: _saving ? null : _pickAvatar,
                            child: const Padding(
                              padding: EdgeInsets.all(6),
                              child: Icon(
                                Icons.camera_alt_outlined,
                                size: 14,
                                color: Colors.white,
                              ),
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          displayName,
                          style: const TextStyle(
                            fontSize: 17,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          email,
                          style: const TextStyle(
                            color: AppTheme.textSubtle,
                            fontSize: 13,
                          ),
                        ),
                        if (city != null && city.trim().isNotEmpty) ...[
                          const SizedBox(height: 2),
                          Text(
                            city,
                            style: const TextStyle(
                              color: AppTheme.textSubtle,
                              fontSize: 13,
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),
            _ActionTile(
              icon: Icons.storefront_outlined,
              title: l.myListings,
              subtitle: l.manageYourListings,
              onTap: () => context.push('/my-listings'),
            ),
            const SizedBox(height: 8),
            _ActionTile(
              icon: Icons.add_box_outlined,
              title: l.createListing,
              subtitle: l.publishNewOffer,
              onTap: () => context.push('/my-listings/create'),
            ),
            const SizedBox(height: 8),
            _ActionTile(
              icon: Icons.local_offer_outlined,
              title: l.promotions,
              subtitle: l.choosePackage,
              onTap: () => context.push('/my-promotions'),
            ),
            const SizedBox(height: 8),
            _ActionTile(
              icon: Icons.receipt_long_outlined,
              title: l.paymentHistory,
              subtitle: l.pay,
              onTap: () => context.push('/payments'),
            ),
            const SizedBox(height: 8),
            _ActionTile(
              icon: Icons.edit_outlined,
              title: l.editProfile,
              subtitle: l.profileUpdated,
              onTap: _showEditProfileSheet,
            ),
            const SizedBox(height: 8),
            _ActionTile(
              icon: Icons.logout,
              title: l.logout,
              subtitle: l.signOutFromAccount,
              iconColor: AppTheme.statusError,
              onTap: _logout,
            ),
          ],
        ),
      ),
    );
  }
}

class _ProfileUpdateDraft {
  const _ProfileUpdateDraft({
    required this.fullName,
    required this.city,
    required this.phone,
    required this.bio,
    required this.preferredLanguage,
  });

  final String fullName;
  final String city;
  final String phone;
  final String bio;
  final String preferredLanguage;

  Map<String, dynamic> toPayload() {
    String? normalize(String value) {
      final trimmed = value.trim();
      if (trimmed.isEmpty) {
        return null;
      }
      return trimmed;
    }

    return {
      'full_name': fullName.trim(),
      'city': normalize(city),
      'phone': normalize(phone),
      'bio': normalize(bio),
      'preferred_language': preferredLanguage,
    };
  }
}

class _EditProfileSheet extends StatefulWidget {
  const _EditProfileSheet({required this.initialProfile});

  final Map<String, dynamic> initialProfile;

  @override
  State<_EditProfileSheet> createState() => _EditProfileSheetState();
}

class _EditProfileSheetState extends State<_EditProfileSheet> {
  late final TextEditingController _nameCtrl;
  late final TextEditingController _cityCtrl;
  late final TextEditingController _phoneCtrl;
  late final TextEditingController _bioCtrl;
  late String _preferredLanguage;

  @override
  void initState() {
    super.initState();
    _nameCtrl = TextEditingController(
      text: widget.initialProfile['full_name']?.toString() ?? '',
    );
    _cityCtrl = TextEditingController(
      text: widget.initialProfile['city']?.toString() ?? '',
    );
    _phoneCtrl = TextEditingController(
      text: widget.initialProfile['phone']?.toString() ?? '',
    );
    _bioCtrl = TextEditingController(
      text: widget.initialProfile['bio']?.toString() ?? '',
    );

    _preferredLanguage =
        (widget.initialProfile['preferred_language']?.toString() ?? 'en')
            .toLowerCase();
    if (_preferredLanguage != 'ru') {
      _preferredLanguage = 'en';
    }
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _cityCtrl.dispose();
    _phoneCtrl.dispose();
    _bioCtrl.dispose();
    super.dispose();
  }

  void _submit() {
    final l = S.of(context)!;
    final fullName = _nameCtrl.text.trim();
    if (fullName.length < 2) {
      ScaffoldMessenger.maybeOf(
        context,
      )?.showSnackBar(SnackBar(content: Text(l.fieldRequired)));
      return;
    }

    Navigator.of(context).pop(
      _ProfileUpdateDraft(
        fullName: fullName,
        city: _cityCtrl.text,
        phone: _phoneCtrl.text,
        bio: _bioCtrl.text,
        preferredLanguage: _preferredLanguage,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l = S.of(context)!;

    return Padding(
      padding: EdgeInsets.fromLTRB(
        16,
        16,
        16,
        MediaQuery.of(context).viewInsets.bottom + 16,
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              l.editProfile,
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _nameCtrl,
              decoration: InputDecoration(labelText: l.fullName),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: _cityCtrl,
              decoration: InputDecoration(labelText: l.city),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: _phoneCtrl,
              decoration: InputDecoration(labelText: l.phone),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: _bioCtrl,
              decoration: InputDecoration(labelText: l.bio),
              maxLines: 3,
            ),
            const SizedBox(height: 10),
            DropdownButtonFormField<String>(
              initialValue: _preferredLanguage,
              decoration: InputDecoration(labelText: l.language),
              onChanged: (value) {
                if (value == null) {
                  return;
                }
                setState(() {
                  _preferredLanguage = value;
                });
              },
              items: const [
                DropdownMenuItem(value: 'en', child: Text('English')),
                DropdownMenuItem(value: 'ru', child: Text('Русский')),
              ],
            ),
            const SizedBox(height: 16),
            ElevatedButton(onPressed: _submit, child: Text(l.save)),
          ],
        ),
      ),
    );
  }
}

class _ActionTile extends StatelessWidget {
  const _ActionTile({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
    this.iconColor,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;
  final Color? iconColor;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: AppTheme.bgSurface,
      borderRadius: BorderRadius.circular(AppTheme.cardRadius),
      child: InkWell(
        borderRadius: BorderRadius.circular(AppTheme.cardRadius),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(AppTheme.cardRadius),
            border: Border.all(color: AppTheme.border),
          ),
          child: Row(
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  color: (iconColor ?? AppTheme.accent).withValues(alpha: 0.12),
                  shape: BoxShape.circle,
                ),
                child: Icon(
                  icon,
                  size: 20,
                  color: iconColor ?? AppTheme.accent,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      subtitle,
                      style: const TextStyle(
                        fontSize: 12,
                        color: AppTheme.textSubtle,
                      ),
                    ),
                  ],
                ),
              ),
              const Icon(Icons.chevron_right, color: AppTheme.textSubtle),
            ],
          ),
        ),
      ),
    );
  }
}
