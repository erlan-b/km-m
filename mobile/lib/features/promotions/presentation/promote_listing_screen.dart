import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:km_marketplace/core/l10n/app_localizations.dart';

import '../../../app/theme.dart';
import '../../listings/data/categories_repository.dart';
import '../../listings/data/listings_repository.dart';
import '../../payments/data/payments_repository.dart';
import '../data/promotions_repository.dart';

class PromoteListingScreen extends ConsumerStatefulWidget {
  const PromoteListingScreen({
    super.key,
    required this.listingId,
    this.initialListing,
  });

  final int listingId;
  final Map<String, dynamic>? initialListing;

  @override
  ConsumerState<PromoteListingScreen> createState() =>
      _PromoteListingScreenState();
}

class _PromoteListingScreenState extends ConsumerState<PromoteListingScreen> {
  final _targetCityCtrl = TextEditingController();

  Map<String, dynamic>? _listing;
  List<Map<String, dynamic>> _packages = [];
  List<Map<String, dynamic>> _categories = [];
  Map<String, dynamic>? _selectedPackage;
  int? _targetCategoryId;

  bool _loading = true;
  bool _submitting = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _listing = widget.initialListing;
    _load();
  }

  @override
  void dispose() {
    _targetCityCtrl.dispose();
    super.dispose();
  }

  bool get _isPublishedListing {
    final status = _listing?['status']?.toString();
    return status == 'published';
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

  String _formatMoney(dynamic amount, String currency) {
    final value = amount is num
        ? amount.toDouble()
        : double.tryParse(amount.toString()) ?? 0;

    final wholePart = value.toInt();
    final buffer = StringBuffer();
    final text = wholePart.toString();

    for (var i = 0; i < text.length; i++) {
      if (i > 0 && (text.length - i) % 3 == 0) {
        buffer.write(' ');
      }
      buffer.write(text[i]);
    }

    return '${buffer.toString()} $currency';
  }

  String _listingStatusLabel(String status, S l) {
    switch (status) {
      case 'published':
        return l.published;
      case 'pending_review':
        return l.pendingReview;
      case 'rejected':
        return l.rejected;
      case 'archived':
        return l.archived;
      case 'draft':
        return l.draft;
      case 'inactive':
        return l.inactive;
      case 'sold':
        return l.sold;
      default:
        return status;
    }
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final result = await Future.wait<dynamic>([
        ref.read(promotionsRepositoryProvider).listPromotionPackages(),
        ref.read(categoriesRepositoryProvider).getCategories(activeOnly: true),
        ref.read(listingsRepositoryProvider).getListing(widget.listingId),
      ]);

      final packages = result[0] as List<Map<String, dynamic>>;
      final rawCategories = result[1] as List<dynamic>;
      final listing = Map<String, dynamic>.from(result[2] as Map);

      final categories = rawCategories
          .whereType<Map>()
          .map((item) => Map<String, dynamic>.from(item))
          .toList();

      final selectedId = (_selectedPackage?['id'] as num?)?.toInt();
      Map<String, dynamic>? nextSelected;

      if (packages.isNotEmpty) {
        if (selectedId != null) {
          for (final item in packages) {
            final itemId = (item['id'] as num?)?.toInt();
            if (itemId == selectedId) {
              nextSelected = item;
              break;
            }
          }
        }
        nextSelected ??= packages.first;
      }

      if (!mounted) {
        return;
      }

      setState(() {
        _packages = packages;
        _categories = categories;
        _listing = listing;
        _selectedPackage = nextSelected;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  Future<void> _payAndActivatePromotion() async {
    final l = S.of(context)!;
    final selectedPackage = _selectedPackage;

    if (selectedPackage == null) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(l.choosePackage)));
      return;
    }

    if (!_isPublishedListing) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(l.pendingReview)));
      return;
    }

    final packageId = (selectedPackage['id'] as num?)?.toInt();
    if (packageId == null) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(l.errorOccurred)));
      return;
    }

    setState(() {
      _submitting = true;
    });

    try {
      final promotion = await ref
          .read(promotionsRepositoryProvider)
          .purchasePromotion(
            listingId: widget.listingId,
            promotionPackageId: packageId,
            targetCity: _targetCityCtrl.text.trim().isEmpty
                ? null
                : _targetCityCtrl.text.trim(),
            targetCategoryId: _targetCategoryId,
          );

      final promotionId = (promotion['id'] as num?)?.toInt();
      if (promotionId == null) {
        throw StateError('Invalid promotion response');
      }

      final amount = promotion['purchased_price'] ?? selectedPackage['price'];
      final currency =
          promotion['currency']?.toString() ??
          selectedPackage['currency']?.toString() ??
          'KGS';

      final payment = await ref
          .read(paymentsRepositoryProvider)
          .createPayment(
            promotionId: promotionId,
            amount: amount,
            currency: currency,
            description: 'Promotion payment for listing ${widget.listingId}',
          );

      final paymentId = (payment['id'] as num?)?.toInt();
      if (paymentId == null) {
        throw StateError('Invalid payment response');
      }

      final providerReference = 'mock-${DateTime.now().millisecondsSinceEpoch}';
      await ref
          .read(paymentsRepositoryProvider)
          .confirmPayment(paymentId, providerReference: providerReference);

      if (!mounted) {
        return;
      }

      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(l.paymentSuccessful)));
      context.go('/my-promotions');
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
          _submitting = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = S.of(context)!;

    if (_loading && _listing == null) {
      return Scaffold(
        appBar: AppBar(title: Text(l.promote)),
        body: const Center(
          child: CircularProgressIndicator(color: AppTheme.accent),
        ),
      );
    }

    if (_error != null && _listing == null) {
      return Scaffold(
        appBar: AppBar(title: Text(l.promote)),
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline, color: AppTheme.textSubtle),
              const SizedBox(height: 12),
              Text(l.errorOccurred),
              const SizedBox(height: 12),
              ElevatedButton(onPressed: _load, child: Text(l.retry)),
            ],
          ),
        ),
      );
    }

    final listing = _listing;
    final selectedPackage = _selectedPackage;
    final selectedPrice = selectedPackage?['price'];
    final selectedCurrency = selectedPackage?['currency']?.toString() ?? 'KGS';

    return Scaffold(
      appBar: AppBar(title: Text(l.promote)),
      body: RefreshIndicator(
        onRefresh: _load,
        color: AppTheme.accent,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 20),
          children: [
            if (listing != null)
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppTheme.bgSurface,
                  borderRadius: BorderRadius.circular(AppTheme.cardRadius),
                  border: Border.all(color: AppTheme.border),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      listing['title']?.toString() ?? '#${widget.listingId}',
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      listing['city']?.toString() ?? '',
                      style: const TextStyle(
                        color: AppTheme.textSubtle,
                        fontSize: 13,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 10,
                        vertical: 5,
                      ),
                      decoration: BoxDecoration(
                        color: AppTheme.bgMuted,
                        borderRadius: BorderRadius.circular(999),
                      ),
                      child: Text(
                        _listingStatusLabel(
                          listing['status']?.toString() ?? '',
                          l,
                        ),
                        style: const TextStyle(
                          fontWeight: FontWeight.w600,
                          color: AppTheme.textSubtle,
                          fontSize: 12,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            if (!_isPublishedListing) ...[
              const SizedBox(height: 10),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppTheme.statusWarningBg,
                  borderRadius: BorderRadius.circular(AppTheme.cardRadius),
                  border: Border.all(color: AppTheme.border),
                ),
                child: Text(
                  l.pendingReview,
                  style: const TextStyle(
                    color: AppTheme.textMain,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
            const SizedBox(height: 16),
            Text(
              l.choosePackage,
              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 8),
            if (_packages.isEmpty)
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppTheme.bgSurface,
                  borderRadius: BorderRadius.circular(AppTheme.cardRadius),
                  border: Border.all(color: AppTheme.border),
                ),
                child: Text(
                  l.emptyList,
                  style: const TextStyle(color: AppTheme.textSubtle),
                ),
              )
            else
              ..._packages.map((item) {
                final packageId = (item['id'] as num?)?.toInt();
                final selectedId = (_selectedPackage?['id'] as num?)?.toInt();
                final title = item['title']?.toString() ?? '-';
                final description = item['description']?.toString() ?? '';
                final durationDays =
                    (item['duration_days'] as num?)?.toInt() ?? 0;
                final price = item['price'];
                final currency = item['currency']?.toString() ?? 'KGS';

                return Container(
                  margin: const EdgeInsets.only(bottom: 8),
                  decoration: BoxDecoration(
                    color: AppTheme.bgSurface,
                    borderRadius: BorderRadius.circular(AppTheme.cardRadius),
                    border: Border.all(color: AppTheme.border),
                  ),
                  child: RadioListTile<int>(
                    value: packageId ?? -1,
                    groupValue: selectedId,
                    onChanged: (_submitting || packageId == null)
                        ? null
                        : (_) {
                            setState(() {
                              _selectedPackage = item;
                            });
                          },
                    title: Text(
                      title,
                      style: const TextStyle(fontWeight: FontWeight.w700),
                    ),
                    subtitle: Text(
                      '${l.duration}: $durationDays ${l.days} · ${_formatMoney(price, currency)}'
                      '${description.trim().isEmpty ? '' : '\n$description'}',
                    ),
                    dense: true,
                    activeColor: AppTheme.accent,
                  ),
                );
              }),
            const SizedBox(height: 16),
            Text(
              l.targetCity,
              style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 6),
            TextField(
              controller: _targetCityCtrl,
              enabled: !_submitting,
              decoration: InputDecoration(hintText: l.targetCity),
            ),
            const SizedBox(height: 14),
            Text(
              l.targetCategory,
              style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 6),
            DropdownButtonFormField<int?>(
              initialValue: _targetCategoryId,
              onChanged: _submitting
                  ? null
                  : (value) {
                      setState(() {
                        _targetCategoryId = value;
                      });
                    },
              decoration: const InputDecoration(),
              items: [
                DropdownMenuItem<int?>(
                  value: null,
                  child: Text(l.allCategories),
                ),
                ..._categories.map((category) {
                  final id = (category['id'] as num?)?.toInt();
                  return DropdownMenuItem<int?>(
                    value: id,
                    child: Text(category['name']?.toString() ?? '-'),
                  );
                }),
              ],
            ),
            if (selectedPackage != null) ...[
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppTheme.accent.withValues(alpha: 0.08),
                  borderRadius: BorderRadius.circular(AppTheme.cardRadius),
                  border: Border.all(
                    color: AppTheme.accent.withValues(alpha: 0.25),
                  ),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      l.price,
                      style: const TextStyle(fontWeight: FontWeight.w700),
                    ),
                    Text(
                      _formatMoney(selectedPrice, selectedCurrency),
                      style: const TextStyle(
                        fontWeight: FontWeight.w800,
                        fontSize: 16,
                      ),
                    ),
                  ],
                ),
              ),
            ],
            const SizedBox(height: 18),
            ElevatedButton.icon(
              onPressed: (_submitting || !_isPublishedListing)
                  ? null
                  : _payAndActivatePromotion,
              icon: const Icon(Icons.bolt_outlined),
              label: _submitting
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : Text(l.pay),
            ),
          ],
        ),
      ),
    );
  }
}
