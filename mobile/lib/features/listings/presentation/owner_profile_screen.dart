import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:km_marketplace/core/l10n/app_localizations.dart';

import '../../../app/theme.dart';

import '../data/public_users_repository.dart';
import 'widgets/listing_card.dart';

class OwnerProfileScreen extends ConsumerStatefulWidget {
  const OwnerProfileScreen({super.key, required this.userId});
  final int userId;

  @override
  ConsumerState<OwnerProfileScreen> createState() => _OwnerProfileScreenState();
}

class _OwnerProfileScreenState extends ConsumerState<OwnerProfileScreen> {
  Map<String, dynamic>? _user;
  List<dynamic> _listings = [];
  bool _loading = true;
  String? _error;
  int _page = 1;
  int _totalPages = 1;

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
      final userRepo = ref.read(publicUsersRepositoryProvider);
      final user = await userRepo.getPublicUser(widget.userId);
      final listingsData = await userRepo.getUserListings(
        widget.userId,
        page: 1,
      );
      setState(() {
        _user = user;
        _listings = listingsData['items'] as List<dynamic>;
        _totalPages = listingsData['total_pages'] as int;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  void _loadMore() {
    if (_page >= _totalPages) return;
    _page++;
    ref
        .read(publicUsersRepositoryProvider)
        .getUserListings(widget.userId, page: _page)
        .then((data) {
          setState(() {
            _listings.addAll(data['items'] as List<dynamic>);
            _totalPages = data['total_pages'] as int;
          });
        });
  }

  @override
  Widget build(BuildContext context) {
    final l = S.of(context)!;

    if (_loading) {
      return Scaffold(
        appBar: AppBar(title: Text(l.ownerProfile)),
        body: const Center(
          child: CircularProgressIndicator(color: AppTheme.accent),
        ),
      );
    }

    if (_error != null || _user == null) {
      return Scaffold(
        appBar: AppBar(title: Text(l.ownerProfile)),
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(l.errorOccurred),
              const SizedBox(height: 12),
              ElevatedButton(onPressed: _load, child: Text(l.retry)),
            ],
          ),
        ),
      );
    }

    final user = _user!;
    final createdAt = DateTime.tryParse(user['created_at'] as String? ?? '');

    return Scaffold(
      appBar: AppBar(title: Text(l.ownerProfile)),
      body: NotificationListener<ScrollNotification>(
        onNotification: (notification) {
          if (notification is ScrollEndNotification &&
              notification.metrics.extentAfter < 200) {
            _loadMore();
          }
          return false;
        },
        child: CustomScrollView(
          slivers: [
            // Profile header
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Row(
                  children: [
                    CircleAvatar(
                      radius: 36,
                      backgroundColor: AppTheme.accent,
                      child: Text(
                        (user['full_name'] as String? ?? '?')[0].toUpperCase(),
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 28,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Flexible(
                                child: Text(
                                  user['full_name'] as String? ?? '',
                                  style: const TextStyle(
                                    fontSize: 20,
                                    fontWeight: FontWeight.w700,
                                  ),
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                              if (user['verified_badge'] == true) ...[
                                const SizedBox(width: 6),
                                const Icon(
                                  Icons.verified,
                                  color: AppTheme.accent,
                                  size: 20,
                                ),
                              ],
                            ],
                          ),
                          if (user['city'] != null)
                            Padding(
                              padding: const EdgeInsets.only(top: 4),
                              child: Row(
                                children: [
                                  const Icon(
                                    Icons.location_on_outlined,
                                    size: 14,
                                    color: AppTheme.textSubtle,
                                  ),
                                  const SizedBox(width: 3),
                                  Text(
                                    user['city'] as String,
                                    style: const TextStyle(
                                      color: AppTheme.textSubtle,
                                      fontSize: 14,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          if (createdAt != null)
                            Padding(
                              padding: const EdgeInsets.only(top: 4),
                              child: Text(
                                '${l.memberSince} ${createdAt.year}.${createdAt.month.toString().padLeft(2, '0')}',
                                style: const TextStyle(
                                  color: AppTheme.textSubtle,
                                  fontSize: 12,
                                ),
                              ),
                            ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),

            // Stats
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    vertical: 12,
                    horizontal: 16,
                  ),
                  decoration: BoxDecoration(
                    color: AppTheme.bgMuted,
                    borderRadius: BorderRadius.circular(AppTheme.cardRadius),
                  ),
                  child: Row(
                    children: [
                      _StatItem(
                        label: l.activeListings,
                        value: '${user['listing_count'] ?? 0}',
                      ),
                      if (user['seller_type'] != null &&
                          user['seller_type'] != 'individual') ...[
                        const SizedBox(width: 24),
                        _StatItem(
                          label: 'Type',
                          value: (user['seller_type'] as String).toUpperCase(),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ),

            // Listings header
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(20, 20, 20, 8),
                child: Text(
                  l.listings,
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ),

            // Listings grid
            if (_listings.isEmpty)
              SliverFillRemaining(
                child: Center(
                  child: Text(
                    l.emptyList,
                    style: const TextStyle(color: AppTheme.textSubtle),
                  ),
                ),
              )
            else
              SliverPadding(
                padding: const EdgeInsets.symmetric(horizontal: 12),
                sliver: SliverGrid(
                  delegate: SliverChildBuilderDelegate((context, index) {
                    final listing = _listings[index] as Map<String, dynamic>;
                    return ListingCard(
                      id: listing['id'] as int,
                      title: listing['title'] as String,
                      price: (listing['price'] is String)
                          ? double.parse(listing['price'] as String)
                          : (listing['price'] as num).toDouble(),
                      currency: listing['currency'] as String,
                      city: listing['city'] as String,
                      transactionType: listing['transaction_type'] as String,
                      isPromoted: listing['is_subscription'] == true,
                      onTap: () => context.push('/listing/${listing['id']}'),
                    );
                  }, childCount: _listings.length),
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: 2,
                    mainAxisSpacing: 12,
                    crossAxisSpacing: 12,
                    childAspectRatio: 0.68,
                  ),
                ),
              ),

            const SliverToBoxAdapter(child: SizedBox(height: 24)),
          ],
        ),
      ),
    );
  }
}

class _StatItem extends StatelessWidget {
  const _StatItem({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(
          value,
          style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
        ),
        const SizedBox(height: 2),
        Text(
          label,
          style: const TextStyle(color: AppTheme.textSubtle, fontSize: 12),
        ),
      ],
    );
  }
}
